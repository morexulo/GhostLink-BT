import sys
import os

# Add the current directory to sys.path so we can import 'src'
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from src.main import main
    if __name__ == "__main__":
        main()
except ImportError as e:
    print(f"Failed to start application: {e}")
    input("Press Enter to close...") # Keep window open if fails
