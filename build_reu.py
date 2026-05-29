import argparse
import os
import sys
import numpy as np

# Version 1

def build_reu_v1(input_file, output_file, reu_size_mb=16):
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
    
    print("Encoding to PDM...")
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

# Version 2

def delta_sigma_first_order_realtime(input_samples, interrupt_interval=65536, stuck_cycles=10):
    """
    Core Delta-Sigma algorithm with Look-Ahead Majority Polling.
    This simulates a real-time stream where a 10-cycle hardware stall 
    causes us to miss 10 cycles of the input target audio.
    """
    N = len(input_samples)
    pdm_out = np.zeros(N, dtype=np.uint8)
    
    acc = 0.0
    i = 0  # Using a while loop to manually advance our time index
    i_out = 0
    while i < N:
        # Check if we've hit the hardware disturbance boundary
        if (i_out + 1) % interrupt_interval == 0:
            
            # 1. Calculate how many cycles we are stuck for (usually 1 + 10 = 11)
            # (We use min() just to prevent indexing out of bounds at the very end of the file)
            window_end = min(i + 1 + stuck_cycles, N)
            actual_stuck_length = window_end - i
            
            # 2. THE MAJORITY POLL: Look ahead at the audio we are about to miss!
            # We sum the input target values over the blind spot.
            target_sum = np.sum(input_samples[i : window_end])
            
            # 3. Choose the optimal stuck bit based on the accumulator + the future sum
            # If the ideal area over the next 11 cycles is positive, we lock onto +1.
            y = 1.0 if (acc + target_sum) >= 0 else -1.0
            
            # 4. Update the accumulator (Feedback)
            # We add the target audio we *wanted* to play, and subtract what 
            # the stuck DAC *actually* played (y * 11).
            acc = acc + target_sum - (y * actual_stuck_length)
            
            # 5. Write the stuck bit to our output array
            pdm_out[i_out] = 1 if y == 1.0 else 0
                
            # 6. Advance 'i' past the stuck cycles (dropping those input samples)
            i += actual_stuck_length
            i_out += 1

        else:
            # --- Normal Delta-Sigma Operation ---
            x = input_samples[i]
            
            # Quantizer
            y = 1.0 if acc + x >= 0 else -1.0  # note: i changed acc -> acc + x to match other case
            
            # Update accumulator
            acc = acc + x - y
            
            # Store bit
            pdm_out[i_out] = 1 if y == 1.0 else 0
            
            # Advance clock tick by 1
            i += 1
            i_out += 1
            
    return pdm_out

def build_reu_v2(input_filepath, output_filepath, reu_size_mb=16):
    """
    Converts 8-bit raw audio to 1-bit PDM-style audio for REU cartridges.
    """
    print(f"Reading 8-bit PCM from {input_filepath}...")
    pcm_bytes = np.fromfile(input_filepath, dtype=np.uint8)
    
    # Map unsigned 8-bit [0, 255] to float [-1.0, 1.0]
    pcm_float = (pcm_bytes.astype(np.float32) / 127.5) - 1.0
    
    print("Encoding to PDM...")
    pdm_bits = delta_sigma_first_order_realtime(pcm_float)
    
    L = reu_size_mb * 1024 * 1024
    output = pdm_bits[:L]
    output = np.pad(output, (0, L - len(output)), mode='constant')
    
    print(f"Writing {L} bytes to {output_filepath}...")
    try:
        with open(output_filepath, 'wb') as f:
            f.write(output.tobytes())
    except IOError as e:
        print(f"Error writing to file: {e}")
        sys.exit(1)
        
    print("Done! Your REU Cartridge image is ready.")


## Main

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
    parser.add_argument( 
        "-v", "--version",
        type=int,
        default=2,
        help="Quantization Version. Version 1 is first-order delta-sigma "
             "modulation. Version 2 is modified version that accounts "
             "for the gaps in playback due to bank switching. (default: 2)"
    )
    args = parser.parse_args()

    # Execute the build process
    if args.version == 1:
        build_reu_v1(args.input_file, args.output_file, args.size)
    else:
        build_reu_v2(args.input_file, args.output_file, args.size)

if __name__ == "__main__":
    main()
