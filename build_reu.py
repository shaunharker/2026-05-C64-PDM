import argparse
import os
import sys

def build_reu(input_file, output_file, reu_size_mb=16):
    """
    Converts 8-bit raw audio to 1-bit PDM-style audio for REU cartridges.
    """
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)

    print(f"Reading {input_file}...")
    with open(input_file, 'rb') as f:
        raw_bytes = f.read()
        
    target_size = reu_size_mb * 1024 * 1024
    output = bytearray(target_size) 
    limit = min(len(raw_bytes), target_size)
    
    print(f"Applying Delta-Sigma Modulation (8-bit to 1-bit)...")
    error = 0
    
    for i in range(limit):
        val = raw_bytes[i] + error
        if val >= 128:
            output[i] = 1        # High state
            error = val - 255
        else:
            output[i] = 0        # Low state
            error = val

    print(f"Writing {target_size} bytes to {output_file}...")
    try:
        with open(output_file, 'wb') as f:
            f.write(output)
    except IOError as e:
        print(f"Error writing to file: {e}")
        sys.exit(1)
        
    print("Done! Your REU Cartridge image is ready.")

def main():
    parser = argparse.ArgumentParser(
        description="Converts 8-bit raw PCM audio into a 1-bit PDM stream "
                    "that may be used as an REU (RAM Expansion Unit) image."
                    "Pads with zeros to desired length (16MiB by default).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example Usage:
  python build_reu.py input.raw -o output.reu
        """
    )

    parser.add_argument(
        "input_file", 
        help="Path to the source 8-bit raw audio file (.raw)"
    )
    parser.add_argument(
        "-o", "--output_file", 
        default="pdm.reu",
        help="Path to the resulting REU cartridge file (.reu)"
    )
    parser.add_argument(
        "-s", "--size", 
        type=int, 
        default=16, 
        help="Target size of the REU image in MB (default: 16)"
    )

    args = parser.parse_args()

    # Execute the build process
    build_reu(args.input_file, args.output_file, args.size)

if __name__ == "__main__":
    main()
