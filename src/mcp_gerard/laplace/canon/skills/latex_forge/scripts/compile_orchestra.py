import sys
import os
import glob
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

def compile_tex(filepath):
    base_dir = os.path.dirname(os.path.abspath(filepath))
    filename = os.path.basename(filepath)
    basename = os.path.splitext(filename)[0]

    def run_cmd(cmd):
        try:
            result = subprocess.run(
                cmd, cwd=base_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            return result.returncode == 0, result.stdout
        except Exception as e:
            return False, str(e)

    pdf_path = os.path.join(base_dir, f"{basename}.pdf")
    if os.path.exists(pdf_path):
        try:
            with open(pdf_path, 'a'):
                pass
        except IOError:
            import time
            subprocess.run(['powershell', '-Command', "Stop-Process -Name Acrobat, AcroRd32, SumatraPDF -ErrorAction SilentlyContinue"], capture_output=True)
            time.sleep(1)
            try:
                with open(pdf_path, 'a'):
                    pass
            except IOError:
                return False, filepath, "ERROR: PDF is locked by another process (possibly Edge/Chrome) and could not be unlocked."

    # 1. pdflatex
    success, out = run_cmd(['pdflatex', '-interaction=nonstopmode', filename])
    if not success:
        return False, filepath, out

    # 2. bibtex
    run_cmd(['bibtex', basename])

    # 3. pdflatex
    run_cmd(['pdflatex', '-interaction=nonstopmode', filename])

    # 4. pdflatex
    success, out = run_cmd(['pdflatex', '-interaction=nonstopmode', filename])
    
    pdf_path = os.path.join(base_dir, f"{basename}.pdf")
    if success and os.path.exists(pdf_path):
        return True, filepath, "Success"
    else:
        return False, filepath, out

def orchestrate_compilation(root_dir):
    if not os.path.isdir(root_dir):
        print(f"Error: {root_dir} is not a directory.")
        return

    tex_files = glob.glob(os.path.join(root_dir, '**', 'main.tex'), recursive=True)
    if not tex_files:
        print(f"No main.tex files found in {root_dir}")
        return

    print(f"Found {len(tex_files)} main.tex files. Commencing global compilation...")
    
    failures = []
    successes = []

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(compile_tex, path): path for path in tex_files}
        
        for future in as_completed(futures):
            success, path, out = future.result()
            if success:
                print(f"[SUCCESS] {path}")
                successes.append(path)
            else:
                print(f"[FAILED]  {path}")
                failures.append((path, out))

    print("\n" + "="*50)
    print("GLOBAL COMPILATION REPORT")
    print("="*50)
    print(f"Total: {len(tex_files)} | Success: {len(successes)} | Failed: {len(failures)}")
    
    if failures:
        print("\nFAILURE DETAILS:")
        for path, out in failures:
            print(f"\n--- {path} ---")
            lines = out.splitlines()
            print('\n'.join(lines[-30:]))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python compile_orchestra.py <target_directory>")
    else:
        orchestrate_compilation(sys.argv[1])
