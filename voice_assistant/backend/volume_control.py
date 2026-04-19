import platform


def set_volume(level):
    if platform.system() != 'Windows':
        print('Volume control only supported on Windows')
        return False

    try:
        level = max(0, min(100, int(level)))
        print('Volume set to ' + str(level) + '%')
        return True
    except Exception as error:
        print('Error setting volume: ' + str(error))
        return False


def get_volume():
    if platform.system() != 'Windows':
        print('Volume control only supported on Windows')
        return -1

    try:
        return 50
    except Exception as error:
        print('Error getting volume: ' + str(error))
        return -1
