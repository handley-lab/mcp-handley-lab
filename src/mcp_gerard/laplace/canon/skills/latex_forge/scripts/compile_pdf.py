import sys
import subprocess
import os
import shutil

def compile_tex(filepath):
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found.")
        return False

    base_dir = os.path.dirname(os.path.abspath(filepath))
    filename = os.path.basename(filepath)
    basename = os.path.splitext(filename)[0]
    jobname = f"{basename}_tmp"

    def run_cmd(cmd):
        try:
            result = subprocess.run(
                cmd, cwd=base_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            if result.returncode != 0:
                print(f"ERROR executing {' '.join(cmd)}:\n")
                lines = result.stdout.splitlines()
                print('\n'.join(lines[-30:]))
                return False
            return True
        except Exception as e:
            print(f"Exception executing {' '.join(cmd)}: {e}")
            return False

    print(f"Commencing full compilation chain for {filename} (compiling to {jobname}.pdf to avoid locks)...")
    
    # 1. pdflatex
    if not run_cmd(['pdflatex', '-interaction=nonstopmode', f'-jobname={jobname}', filename]):
        return False
        
    # 2. bibtex
    run_cmd(['bibtex', jobname])
    
    # 3. pdflatex
    if not run_cmd(['pdflatex', '-interaction=nonstopmode', f'-jobname={jobname}', filename]):
        return False
        
    # 4. pdflatex
    if not run_cmd(['pdflatex', '-interaction=nonstopmode', f'-jobname={jobname}', filename]):
        return False

    pdf_path_tmp = os.path.join(base_dir, f"{jobname}.pdf")
    pdf_path = os.path.join(base_dir, f"{basename}.pdf")
    
    if os.path.exists(pdf_path_tmp):
        try:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            shutil.move(pdf_path_tmp, pdf_path)
            print(f"\nSUCCESS: PDF securely compiled at {pdf_path}")
            
            # Clean up aux files from tmp job
            for ext in ['.aux', '.log', '.out', '.blg', '.bbl', '.toc']:
                aux_file = os.path.join(base_dir, f"{jobname}{ext}")
                if os.path.exists(aux_file):
                    os.remove(aux_file)
                    
            return True
        except Exception as e:
            print(f"ERROR: PDF compiled to {pdf_path_tmp}, but could not replace {pdf_path} due to error: {e}. The file might be locked by a viewer.")
            return False
    else:
        print("\nFAILURE: PDF not generated despite no explicit error from pdflatex.")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python compile_pdf.py <path_to_tex_file>")
    else:
        success = compile_tex(sys.argv[1])
        sys.exit(0 if success else 1)
