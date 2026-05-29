import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="Banish pedagogical math to an appendix.")
    parser.add_argument('--source', required=True, help="Absolute path to the source .tex file")
    parser.add_argument('--start', type=int, required=True, help="Start line number (1-indexed)")
    parser.add_argument('--end', type=int, required=True, help="End line number (1-indexed)")
    parser.add_argument('--target', required=True, help="Absolute path to the target appendix .tex file")
    parser.add_argument('--ref', required=True, help="The reference string to leave behind in the source file")
    
    args = parser.parse_args()
    
    if args.start < 1 or args.end < args.start:
        print("Error: Invalid line range.", file=sys.stderr)
        sys.exit(1)

    # Read source file
    try:
        with open(args.source, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading source file: {e}", file=sys.stderr)
        sys.exit(1)
        
    if args.end > len(lines):
        print(f"Error: End line {args.end} exceeds source file length {len(lines)}.", file=sys.stderr)
        sys.exit(1)

    # Extract banished content
    # Line numbers are 1-indexed, so start-1 to end
    banished_content = lines[args.start-1:args.end]
    
    # Form the new source content
    new_source_lines = lines[:args.start-1] + [args.ref + "\n"] + lines[args.end:]
    
    # Write updated source file
    try:
        with open(args.source, 'w', encoding='utf-8') as f:
            f.writelines(new_source_lines)
    except Exception as e:
        print(f"Error writing to source file: {e}", file=sys.stderr)
        sys.exit(1)
        
    # Append to target appendix
    try:
        with open(args.target, 'a', encoding='utf-8') as f:
            f.write("\n% --- Migrated Content ---\n")
            f.writelines(banished_content)
            f.write("\n")
    except Exception as e:
        print(f"Error appending to target file: {e}", file=sys.stderr)
        # Attempt to rollback source file? (Omitted for simplicity, rely on git_mechanic for safety)
        sys.exit(1)

    print(f"Success: Banished lines {args.start}-{args.end} from {args.source} to {args.target}.")

if __name__ == "__main__":
    main()
