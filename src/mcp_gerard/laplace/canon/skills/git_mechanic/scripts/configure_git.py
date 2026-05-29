import os
import subprocess
import sys

def configure_git():
    print("Configuring Git to bypass Windows MAX_PATH limits...")
    
    try:
        # Enable longpaths globally
        subprocess.run(["git", "config", "--global", "core.longpaths", "true"], check=True)
        print("[SUCCESS] Global git config updated: core.longpaths=true.")
        
        # Try to enable locally as well, just in case
        if os.path.isdir(".git"):
            subprocess.run(["git", "config", "core.longpaths", "true"], check=True)
            print("[SUCCESS] Local git config updated: core.longpaths=true.")
        else:
            print("[INFO] Not in a git repository, skipping local config.")
            
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to configure Git: {e}")
        sys.exit(1)

if __name__ == "__main__":
    configure_git()
