"""
Volume Control Module for Windows
Provides functions to get and set system volume using pycaw.
"""

import ctypes
import logging
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from pycaw.utils import AudioSession

logger = logging.getLogger(__name__)


def get_volume():
    """
    Get current system volume level (0-100).
    
    Returns:
        int: Current volume level (0-100), or None if error occurs
    """
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, ctypes.POINTER(IAudioEndpointVolume), None)
        volume = interface.QueryInterface(IAudioEndpointVolume)
        
        # Get volume in scalar range (0.0 to 1.0)
        current_volume = volume.GetMasterVolumeLevelScalar()
        
        # Convert to percentage (0-100)
        volume_percent = int(current_volume * 100)
        
        logger.info(f"Current volume: {volume_percent}%")
        return volume_percent
        
    except Exception as e:
        logger.error(f"Error getting volume: {e}")
        return None


def set_volume(level):
    """
    Set system volume level.
    
    Args:
        level: Volume level as integer (0-100) or float (0.0-1.0)
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Convert to 0.0-1.0 range if given as percentage
        if level > 1.0:
            level = level / 100.0
        
        # Clamp to valid range
        level = max(0.0, min(1.0, level))
        
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, ctypes.POINTER(IAudioEndpointVolume), None)
        volume = interface.QueryInterface(IAudioEndpointVolume)
        
        # Set volume
        volume.SetMasterVolumeLevelScalar(level, None)
        
        logger.info(f"Volume set to {int(level * 100)}%")
        return True
        
    except Exception as e:
        logger.error(f"Error setting volume: {e}")
        return False


def mute_volume():
    """
    Mute system volume.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, ctypes.POINTER(IAudioEndpointVolume), None)
        volume = interface.QueryInterface(IAudioEndpointVolume)
        
        volume.SetMute(1, None)
        logger.info("Volume muted")
        return True
        
    except Exception as e:
        logger.error(f"Error muting volume: {e}")
        return False


def unmute_volume():
    """
    Unmute system volume.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, ctypes.POINTER(IAudioEndpointVolume), None)
        volume = interface.QueryInterface(IAudioEndpointVolume)
        
        volume.SetMute(0, None)
        logger.info("Volume unmuted")
        return True
        
    except Exception as e:
        logger.error(f"Error unmuting volume: {e}")
        return False


def increase_volume(step=10):
    """
    Increase volume by specified step.
    
    Args:
        step: Amount to increase in percentage (default: 10)
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        current = get_volume()
        if current is not None:
            new_level = min(100, current + step)
            return set_volume(new_level)
        return False
    except Exception as e:
        logger.error(f"Error increasing volume: {e}")
        return False


def decrease_volume(step=10):
    """
    Decrease volume by specified step.
    
    Args:
        step: Amount to decrease in percentage (default: 10)
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        current = get_volume()
        if current is not None:
            new_level = max(0, current - step)
            return set_volume(new_level)
        return False
    except Exception as e:
        logger.error(f"Error decreasing volume: {e}")
        return False
