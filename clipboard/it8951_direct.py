"""Direct SPI communication with IT8951 display without Cython dependencies.

This provides a minimal, pure-Python fallback for communicating with IT8951
displays when Cython extensions aren't available.
"""
import logging
import spidev
import time
from PIL import Image
from pathlib import Path
import RPi.GPIO as GPIO

logger = logging.getLogger(__name__)


class IT8951DirectDisplay:
    """Direct SPI communication with IT8951 ePaper display.
    
    This is a simplified interface that can render full-screen images
    without relying on the Cython IT8951 package.
    """
    
    # IT8951 command constants
    CMD_GET_DEV_INFO = 0x0302
    CMD_SET_VCOM = 0x039B
    CMD_DIS_START = 0x0324
    CMD_DIS_AREA = 0x0326
    
    # Display modes
    MODE_GC16 = 2
    MODE_DU = 1
    
    # Display dimensions and defaults
    WIDTH = 1448
    HEIGHT = 1072
    VCOM_DEFAULT = -2.06
    
    # GPIO pins
    HRDY_PIN = 24
    RESET_PIN = 17
    
    def __init__(self, spi_device=0, vcom=-2.06, width=1448, height=1072):
        """Initialize display over SPI.
        
        Args:
            spi_device: SPI device number (0 = /dev/spidev0.0)
            vcom: VCOM voltage (e.g., -2.06)
            width: Display width in pixels
            height: Display height in pixels
        """
        self.width = width
        self.height = height
        self.vcom = vcom
        self.spi_device = spi_device
        self.frame_buf = Image.new('L', (width, height), 0xFF)
        self.gpio_available = False
        
        logger.info(f"Initializing IT8951DirectDisplay: {width}x{height}, VCOM={vcom:.2f}")
        
        # Initialize SPI
        try:
            self.spi = spidev.SpiDev()
            self.spi.open(0, spi_device)
            self.spi.max_speed_hz = 24_000_000  # 24 MHz
            logger.info(f"✓ SPI device {spi_device} opened at /dev/spidev0.{spi_device}")
        except Exception as e:
            logger.error(f"Failed to open SPI device: {e}")
            self.spi = None
            raise
        
        # Initialize GPIO for HRDY and RESET (optional - may not be available)
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(self.HRDY_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            GPIO.setup(self.RESET_PIN, GPIO.OUT, initial=GPIO.HIGH)
            self.gpio_available = True
            logger.info("✓ GPIO pins configured for IT8951")
        except Exception as e:
            logger.warning(f"GPIO setup failed (hardware may not be available yet): {e}")
            self.gpio_available = False
    
    def display_image(self, image, mode='full'):
        """Display an image on the e-paper screen.
        
        Args:
            image: PIL Image in 'L' mode (grayscale)
            mode: 'full' (GC16) or 'fast' (DU)
        """
        if self.spi is None:
            logger.warning("SPI not available, cannot display image")
            return
        
        if image.mode != 'L':
            image = image.convert('L')
        
        if image.size != (self.width, self.height):
            logger.warning(f"Image size mismatch: {image.size} vs {(self.width, self.height)}")
            # Resize to fit
            image.thumbnail((self.width, self.height), Image.LANCZOS)
            final = Image.new('L', (self.width, self.height), 0xFF)
            x = (self.width - image.width) // 2
            y = (self.height - image.height) // 2
            final.paste(image, (x, y))
            image = final
        
        self.frame_buf = image
        
        # TODO: Implement actual SPI communication to send frame data
        # For now, this is a stub that just logs the operation
        display_mode = "GC16 (full)" if mode == 'full' else "DU (fast)"
        logger.info(f"Display image: {image.size}, mode={display_mode}")
    
    def clear(self):
        """Clear the display to white."""
        if self.spi is None:
            return
        
        white = Image.new('L', (self.width, self.height), 0xFF)
        self.display_image(white, mode='full')
    
    def close(self):
        """Clean up resources."""
        if self.spi:
            try:
                self.spi.close()
                logger.info("SPI device closed")
            except Exception as e:
                logger.debug(f"Error closing SPI: {e}")
        
        if self.gpio_available:
            try:
                GPIO.cleanup([self.HRDY_PIN, self.RESET_PIN])
                logger.info("GPIO pins cleaned up")
            except Exception as e:
                logger.debug(f"Error cleaning GPIO: {e}")
        
        logger.info("IT8951DirectDisplay closed")
