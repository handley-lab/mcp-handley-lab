import os
import subprocess
import sys

def safe_revert(commit_hash):
    print(f"Attempting to safely revert commit {commit_hash}...")
    
    # Check if we are in a clean state
    status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    if status.stdout.strip():
        print("[ERROR] Working tree is not clean. Commit or stash changes before reverting.")
        sys.exit(1)
        
    try:
        # Run git revert with no-edit to avoid hanging on the commit message
        result = subprocess.run(["git", "revert", "--no-edit", commit_hash], capture_output=True, text=True)
        
        if result.returncode != 0:
            print("[WARNING] Revert failed due to conflicts. Aborting revert to prevent corrupted state...")
            print("Git Output:")
            print(result.stdout)
            print(result.stderr)
            
            # Abort the revert
            abort_result = subprocess.run(["git", "revert", "--abort"], capture_output=True, text=True)
            if abort_result.returncode == 0:
                print("[SUCCESS] Revert cleanly aborted. The working tree is back to normal.")
                print("Advice: Use `git restore --source=<commit> <file>` if you only need specific files.")
            else:
                print("[CRITICAL ERROR] Failed to abort the revert. Repository may be stuck in reverting state.")
            sys.exit(1)
            
        else:
            print(f"[SUCCESS] Successfully reverted commit {commit_hash}.")
            
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python safe_revert.py <commit_hash>")
        sys.exit(1)
        
    commit_hash = sys.argv[1]
    safe_revert(commit_hash)
