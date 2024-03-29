import time
from datetime import datetime

HEADER = "\033[95m"  # Purple
OKBLUE = "\033[94m"  # Blue
OKCYAN = "\033[96m"  # Cyan
OKGREEN = "\033[92m"  # Green
WARNING = "\033[93m"  # Yellow
FAIL = "\033[91m"  # Red

ENDC = "\033[0m"  # End color
BOLD = "\033[1m"  # Bold
UNDERLINE = "\033[4m"  # Underline


def logger(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        print(f"{HEADER}Starting {func.__name__}()...{ENDC}")
        current_time = datetime.now().strftime("%H:%M:%S")
        try:
            result = func(*args, **kwargs)
            end_time = time.time()
            print(
                f"{OKCYAN}{current_time} [INFO] {BOLD}{func.__name__}() took {round(end_time - start_time, 3)} seconds.{ENDC}"
            )
            return result
        except Exception as e:
            print(f"{FAIL}{current_time} [ERROR] {BOLD}{func.__name__}()\n{e}{ENDC}")
            return

    return wrapper


def info(*args):
    current_time = datetime.now().strftime("%H:%M:%S")
    print(f"{OKGREEN}{current_time} [INFO]", *args, ENDC)


def error(*args):
    current_time = datetime.now().strftime("%H:%M:%S")
    print(f"{FAIL}{current_time} [ERROR]", *args, ENDC)


def warn(*args):
    current_time = datetime.now().strftime("%H:%M:%S")
    print(f"{WARNING}{current_time} [WARN]", *args, ENDC)


def emphasize(*args):
    current_time = datetime.now().strftime("%H:%M:%S")
    print(f"{BOLD}{OKBLUE}{current_time} [INFO]", *args, ENDC)
