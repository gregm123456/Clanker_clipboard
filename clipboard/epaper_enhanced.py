"""Enhanced standalone e-paper driver that can optionally use IT8951 package.

This provides a self-contained fallback while allowing use of the IT8951 package
when available for better hardware support.
"""
import logging
from typing import Union, Optional
from pathlib import Path
from PIL import Image
import sys

logger = logging.getLogger(__name__)

# Determine project root once
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
clipboard_dir = current_file.parent

# Try to import display drivers in order of preference
DISPLAY_MODE = "none"
update_waveshare_available = False
IT8951_AVAILABLE = False


# Do NOT manually add IT8951/src to sys.path — the venv-installed IT8951
# package includes compiled Cython extensions (.so) and must take precedence
# over any local source tree which has no compiled extensions.

# Try update_waveshare (most likely to work)
try:
    logger.info(f"Looking for update_waveshare in: {project_root}")
    
    # Add project root to path so we can import update_waveshare
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    from update_waveshare.core import blank_screen
    from update_waveshare._device import create_device as create_waveshare_device
    from IT8951.constants import DisplayModes, PixelModes
    update_waveshare_available = True
    DISPLAY_MODE = "update_waveshare"
    logger.info("✓ update_waveshare available - using existing drivers")
except ImportError as e:
    logger.info(f"✗ update_waveshare not available: {e}")

# Fallback to IT8951 if update_waveshare fails
# Do NOT add local IT8951/src to sys.path — venv-installed IT8951 1.0.0 has compiled .so extensions
if not update_waveshare_available:
    try:
        from IT8951.display import AutoEPDDisplay, VirtualEPDDisplay
        from IT8951.constants import DisplayModes
        IT8951_AVAILABLE = True
        DISPLAY_MODE = "IT8951"
        logger.info("✓ IT8951 package available - using enhanced driver")
    except ImportError as e:
        logger.info(f"✗ IT8951 package not available: {e}")

# Fallback to our basic SPI implementation
try:
    import spidev
    SPI_AVAILABLE = True
except ImportError:
    SPI_AVAILABLE = False


class WaveshareDisplay:
    """Display using existing update_waveshare drivers."""
    
    def __init__(self, spi_device=0, vcom=-2.06, width=1448, height=1072, virtual=False):
        self.width = width
        self.height = height
        self.virtual = virtual
        self._needs_init = True
        
        if update_waveshare_available:
            try:
                self.device = create_waveshare_device(vcom=vcom, virtual=virtual)
                self.width = getattr(self.device, 'width', width)
                self.height = getattr(self.device, 'height', height)
                logger.info(f"Waveshare display initialized: {self.width}x{self.height}")
            except Exception as e:
                logger.error(f"Failed to create waveshare device: {e}")
                raise
        else:
            raise RuntimeError("update_waveshare not available")
    
    def clear(self):
        """Clear the display."""
        logger.info("Clearing display (waveshare)")
        if update_waveshare_available:
            try:
                blank_screen(device=self.device, virtual=self.virtual)
                self._needs_init = False
            except Exception as e:
                logger.error(f"Clear failed: {e}")
    
    def display_image(self, image: Union[Image.Image, str], mode='auto'):
        """Display an image."""
        if isinstance(image, str):
            img = Image.open(image)
        else:
            img = image.copy()
        
        try:
            if mode in ('auto', 'full', 'full_quality') and self._needs_init:
                logger.info("Priming panel with INIT clear before first full refresh")
                self.device.clear()
                self._needs_init = False

            prepared = self._prepare_image(img)
            self.device.frame_buf.paste(prepared)

            logger.info(f"Displaying image with direct waveshare path (mode: {mode})")
            if mode == 'FAST':
                self.device.draw_full(DisplayModes.DU)
            else:
                frame = self.device._get_frame_buf()
                self.device.update(
                    frame.tobytes(),
                    (0, 0),
                    self.device.display_dims,
                    DisplayModes.GC16,
                    pixel_format=PixelModes.M_8BPP,
                )
                self.device.prev_frame = frame

            regions = [(0, 0, self.width, self.height)]
            logger.info(f"Display update completed, regions: {regions}")
        except Exception as e:
            logger.error(f"Display update failed: {e}")
            raise

    def _prepare_image(self, img: Image.Image) -> Image.Image:
        """Prepare image for full-screen display."""
        if img.mode != 'L':
            img = img.convert('L')

        img.thumbnail((self.width, self.height), Image.LANCZOS)

        prepared = Image.new('L', (self.width, self.height), 0xFF)
        x = (self.width - img.width) // 2
        y = (self.height - img.height) // 2
        prepared.paste(img, (x, y))
        return prepared
    
    def close(self):
        """Close display connection."""
        if hasattr(self.device, 'epd') and hasattr(self.device.epd, 'standby'):
            try:
                self.device.epd.standby()
            except:
                pass
        logger.info("Waveshare display closed")


class EnhancedIT8951Display:
    """Enhanced display using IT8951 package when available."""
    
    def __init__(self, spi_device=0, vcom=-2.06, width=1448, height=1072, virtual=False):
        self.width = width
        self.height = height
        self.virtual = virtual
        
        if IT8951_AVAILABLE:
            if virtual:
                self.display = VirtualEPDDisplay(dims=(width, height))
            else:
                self.display = AutoEPDDisplay(vcom=vcom)
                self.width = self.display.width
                self.height = self.display.height
            logger.info(f"Enhanced display initialized: {self.width}x{self.height}")
        else:
            raise RuntimeError("IT8951 package not available for enhanced driver")
    
    def clear(self):
        """Clear the display."""
        logger.info("Clearing display")
        if hasattr(self.display, 'clear'):
            self.display.clear()
        else:
            # Fallback: fill with white and update
            self.display.frame_buf = Image.new('L', (self.width, self.height), 0xFF)
            if IT8951_AVAILABLE:
                self.display.draw_full(DisplayModes.GC16)
    
    def display_image(self, image: Union[Image.Image, str], mode='auto'):
        """Display an image."""
        if isinstance(image, str):
            img = Image.open(image)
        else:
            img = image.copy()
        
        # Prepare image
        prepared = self._prepare_image(img)
        
        # Update display
        self.display.frame_buf.paste(prepared)
        
        if mode == 'auto' or mode == 'full':
            if IT8951_AVAILABLE:
                # Use GC16 for proper grayscale rendering (images need this)
                self.display.draw_full(DisplayModes.GC16)
        elif mode == 'partial':
            if IT8951_AVAILABLE:
                self.display.draw_partial(DisplayModes.DU)
        elif mode == 'FAST':
            if IT8951_AVAILABLE:
                # Lightning-fast DU-only mode for menus
                self.display.draw_partial(DisplayModes.DU)
        
        logger.info(f"Display updated with mode {mode}")
    
    def _prepare_image(self, img: Image.Image) -> Image.Image:
        """Prepare image for display."""
        if img.mode != 'L':
            img = img.convert('L')
        
        img.thumbnail((self.width, self.height), Image.LANCZOS)
        
        prepared = Image.new('L', (self.width, self.height), 0xFF)
        x = (self.width - img.width) // 2
        y = (self.height - img.height) // 2
        prepared.paste(img, (x, y))
        
        return prepared
    
    def close(self):
        """Close display connection."""
        if hasattr(self.display, 'epd') and hasattr(self.display.epd, 'standby'):
            try:
                self.display.epd.standby()
            except:
                pass
        logger.info("Display closed")


class BasicSPIDisplay:
    """Basic SPI display implementation."""
    
    def __init__(self, spi_device=0, vcom=-2.06, width=1448, height=1072):
        self.width = width
        self.height = height
        self.frame_buf = Image.new('L', (width, height), 0xFF)
        
        if SPI_AVAILABLE:
            self.spi = spidev.SpiDev()
            self.spi.open(0, spi_device)
            self.spi.max_speed_hz = 24000000
            self.spi.mode = 0
            logger.info(f"Basic SPI display initialized on CE{spi_device}")
        else:
            self.spi = None
            logger.warning("SPI not available - display will not update")
    
    def clear(self):
        """Clear display to white."""
        logger.info("Clearing display (basic SPI)")
        self.frame_buf = Image.new('L', (self.width, self.height), 0xFF)
        logger.info("Display cleared (basic mode)")
    
    def display_image(self, image: Union[Image.Image, str], mode='auto'):
        """Display an image."""
        if isinstance(image, str):
            img = Image.open(image)
        else:
            img = image.copy()
        
        prepared = self._prepare_image(img)
        self.frame_buf = prepared
        
        logger.info(f"Image prepared for display (basic SPI mode: {mode})")
    
    def _prepare_image(self, img: Image.Image) -> Image.Image:
        """Prepare image for display."""
        if img.mode != 'L':
            img = img.convert('L')
        
        img.thumbnail((self.width, self.height), Image.LANCZOS)
        
        prepared = Image.new('L', (self.width, self.height), 0xFF)
        x = (self.width - img.width) // 2
        y = (self.height - img.height) // 2
        prepared.paste(img, (x, y))
        
        return prepared
    
    def close(self):
        """Close SPI connection."""
        if self.spi:
            self.spi.close()
        logger.info("Basic SPI display closed")


class SimulatedDisplay:
    """Simulated display for development."""
    
    def __init__(self, width=1448, height=1072):
        self.width = width
        self.height = height
        self.frame_buf = Image.new('L', (width, height), 0xFF)
        self.output_dir = Path("/tmp/clipboard_display")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.frame_count = 0
        
    def clear(self):
        logger.info("Simulated: Clearing display")
        self.frame_buf = Image.new('L', (self.width, self.height), 0xFF)
        self._save_frame("clear")
    
    def display_image(self, image: Union[Image.Image, str], mode='auto'):
        if isinstance(image, str):
            img = Image.open(image)
        else:
            img = image.copy()
            
        if img.mode != 'L':
            img = img.convert('L')
        
        img.thumbnail((self.width, self.height), Image.LANCZOS)
        prepared = Image.new('L', (self.width, self.height), 0xFF)
        x = (self.width - prepared.width) // 2
        y = (self.height - prepared.height) // 2
        prepared.paste(img, (x, y))
        
        self.frame_buf = prepared
        self._save_frame(f"display_{mode}")
        logger.info(f"Simulated: Display image with mode {mode}")
    
    def _save_frame(self, label="frame"):
        filename = self.output_dir / f"{label}_{self.frame_count:04d}.png"
        self.frame_buf.save(filename)
        self.frame_count += 1
        logger.info(f"Saved simulated frame to {filename}")
    
    def close(self):
        logger.info("Simulated: Display closed")


def create_display(spi_device=0, vcom=-2.06, width=1448, height=1072, force_simulation=False, prefer_enhanced=True):
    """Create the best available display instance.
    
    Args:
        spi_device: SPI device number (0 for CE0, 1 for CE1)
        vcom: VCOM voltage
        width: Display width
        height: Display height
        force_simulation: Force simulation mode
        prefer_enhanced: Prefer advanced drivers if available
    
    Returns:
        Display instance
    """
    if force_simulation:
        logger.info("Creating simulated display")
        return SimulatedDisplay(width, height)
    
    # Try update_waveshare first (most likely to work)
    if prefer_enhanced and update_waveshare_available:
        try:
            logger.info(f"Creating Waveshare display on SPI device {spi_device}")
            return WaveshareDisplay(spi_device=spi_device, vcom=vcom, width=width, height=height)
        except Exception as e:
            logger.warning(f"Waveshare display failed: {e} - trying next option")
    
    # Try IT8951 as fallback
    if prefer_enhanced and IT8951_AVAILABLE:
        try:
            logger.info(f"Creating enhanced IT8951 display on SPI device {spi_device}")
            return EnhancedIT8951Display(spi_device=spi_device, vcom=vcom, width=width, height=height)
        except Exception as e:
            logger.warning(f"Enhanced display failed: {e} - trying direct SPI")
    
    # Try pure Python IT8951 direct SPI (no Cython)
    try:
        logger.info(f"Creating IT8951DirectDisplay (pure Python SPI) on device {spi_device}")
        from clipboard.it8951_direct import IT8951DirectDisplay
        return IT8951DirectDisplay(spi_device=spi_device, vcom=vcom, width=width, height=height)
    except Exception as e:
        logger.warning(f"IT8951DirectDisplay failed: {e} - falling back to basic SPI")
    
    # Basic SPI as last resort
    if SPI_AVAILABLE:
        logger.info(f"Creating basic SPI display on device {spi_device}")
        return BasicSPIDisplay(spi_device=spi_device, vcom=vcom, width=width, height=height)
    else:
        logger.info("No SPI available - creating simulated display")
        return SimulatedDisplay(width, height)
