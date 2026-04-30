"""Minimal shims to allow IT8951 to be imported even when Cython modules aren't built.

This provides stub implementations of Cython-based img_manip and spi functions using pure Python.
Used as a fallback when IT8951 Cython extensions can't be imported.
"""
import logging
from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)


def make_changes_bw(diff_image, buf):
    """Convert PIL Image differences to IT8951 frame buffer format.
    
    This is a pure Python fallback for the Cython version.
    The IT8951 display uses 4-bit (16-level) grayscale.
    Each byte encodes two pixels.
    
    Args:
        diff_image: PIL Image in L mode (grayscale)
        buf: Bytearray or bytes to write pixel data to
    """
    # Convert image to numpy array for faster processing
    if diff_image.mode != 'L':
        diff_image = diff_image.convert('L')
    
    img_array = np.array(diff_image, dtype=np.uint8)
    
    # Quantize to 4-bit (16 levels)
    # IT8951 uses 0-15 for 16 levels of gray
    quantized = (img_array >> 4) & 0x0F
    
    # Pack two 4-bit pixels into each byte
    # Format: high nibble is pixel[0], low nibble is pixel[1]
    flat = quantized.flatten()
    
    # Pack pairs of pixels
    for i in range(0, len(flat), 2):
        if i + 1 < len(flat):
            byte_val = (flat[i] << 4) | flat[i + 1]
        else:
            byte_val = (flat[i] << 4)
        buf[i // 2] = byte_val


def quick_display_mode_value(mode):
    """Convert display mode to raw value if needed.
    
    Args:
        mode: DisplayMode enum or integer
        
    Returns:
        Integer display mode value
    """
    if hasattr(mode, 'value'):
        return mode.value
    return int(mode)


# SPI shim functions - stubs for Cython IT8951.spi module
class SPI:
    """Stub class for IT8951 SPI interface.
    
    Mimics the Cython SPI class from IT8951.spi but provides stub methods
    that don't actually communicate with hardware.
    """
    
    def __init__(self, bus=0, device=0, cmd_hz=24_000_000, data_hz=24_000_000, timeout_secs=5):
        logger.warning(f"Using IT8951 SPI stub - hardware communication may be limited")
        self.bus = bus
        self.device = device
        self.cmd_hz = cmd_hz
        self.data_hz = data_hz
        self.timeout_secs = timeout_secs
    
    def writebytes(self, data):
        """Stub: pretend to write bytes via SPI."""
        pass
    
    def readbytes(self, length):
        """Stub: pretend to read bytes via SPI."""
        return b'\x00' * length
    
    def writebytes2(self, data):
        """Stub: pretend to write 2-byte SPI transfers."""
        pass
    
    def xfer2(self, data):
        """Stub: full-duplex SPI transfer."""
        return b'\x00' * len(data)
    
    def wait_ready(self):
        """Stub: pretend to wait for ready signal."""
        pass
    
    def transfer(self, size, speed):
        """Stub: pretend to perform SPI transfer."""
        pass
    
    def read(self, preamble, count):
        """Stub: pretend to read data via SPI."""
        return [0] * count
    
    def write(self, preamble, data):
        """Stub: pretend to write data via SPI."""
        pass
    
    def write_image(self, img_data):
        """Stub: pretend to write image data."""
        pass


class SPIStub:
    """Deprecated alias for SPI."""
    
    def __init__(self, bus=0, device=0, freq=24_000_000):
        logger.warning(f"Using SPI stub - hardware communication will be ineffective")
        self.bus = bus
        self.device = device
        self.freq = freq
    
    def writebytes(self, data):
        """Stub: pretend to write bytes via SPI."""
        pass
    
    def readbytes(self, length):
        """Stub: pretend to read bytes via SPI."""
        return b'\x00' * length
    
    def writebytes2(self, data):
        """Stub: pretend to write 2-byte SPI transfers."""
        pass
    
    def xfer2(self, data):
        """Stub: full-duplex SPI transfer."""
        return b'\x00' * len(data)


def get_spi_interface(bus=0, device=0, freq=24_000_000):
    """Factory for SPI interface - returns stub when Cython isn't available."""
    try:
        import spidev
        return spidev.SpiDev()
    except ImportError:
        logger.warning("spidev not available, using SPI stub")
        return SPI(bus=bus, device=device, freq=freq)

