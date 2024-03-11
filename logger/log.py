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
        print(f"{HEADER}Starting {func.__name__}...{ENDC}")
        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")
        try:
            result = func(*args, **kwargs)
            end_time = time.time()
            print(
                f"{OKCYAN}{current_time} {BOLD}{func.__name__} took {round(end_time - start_time, 3)} seconds.{ENDC}"
            )
            return result
        except Exception as e:
            print(f"{FAIL}{current_time} [ERROR] {BOLD}{func.__name__}\n{e}{ENDC}")
            return

    return wrapper


def info(content: str):
    print(f"[INFO] {OKBLUE}{content}{ENDC}")
