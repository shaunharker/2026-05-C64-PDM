## Pulse Density Modulation (PDM) on a Commodore 64

## Overview

This is a C64 project to abuse the SID's `$d402` register in order to achieve 1MHz 1-bit PDM playback.

PDM is described here:

https://en.wikipedia.org/wiki/Pulse-density_modulation

It might also be referred to as a 1-bit DAC:

https://en.wikipedia.org/wiki/1-bit_DAC

Here are a few other related articles:

https://en.wikipedia.org/wiki/Delta-sigma_modulation

https://en.wikipedia.org/wiki/Direct_Stream_Digital

https://en.wikipedia.org/wiki/Super_Audio_CD

### Key facts

* This technique turns audio into a file consisting only of the values 0 and 1, corresponding to a quantized ~1MHz sampling.
* PDM is the encoding used in Sony's Super Audio CD (SACD) format, under the name Direct Stream Digital. It was released in 1999. they used 1-bit, 2.8224 MHz. Apparently it is popular among audiophiles, but did not get broader market adoption.

### Regarding the current C64 demonstration

* This code lets you play back 16 second samples on a C64 that are rather high quality except they have a 'ticking' sound in the background.
* The method is to exploit a cartridge REU's DMA (RAM Expansion Unit Direct Memory Access) to blast the samples (the 0 and 1 bytes) into the `$d402` SID register that controls pulse wave width at the full clock speed of the C64 (~1MHz). The code configures the SID so that the resulting waveform is directly the sequence given, resulting in 1MHz 1-bit PDM on a 1982 machine. (Not that anyone had a 16MiB REU in the 1980s, which only holds enough for 16 seconds of audio using this technique. Technically we could store 8 times as much audio if we packed the bits into the bytes in a sensible way, but then we couldn't use the DMA trick to get such a fast sampling rate.)
* The DMA is only in 64KiB chunks and this causes a ~15Hz 'ticking' sound due to bank switching code. What is happening is that during the 10 cycles where the 6510 is setting up the next DMA, no new data is being sent to `$d402`, and it remains 'stuck' at whatever value it was left at. These disruptions in playback, lasting for 10 microseconds each and repeated fifteen times a second, result in audible ticking. To mitigate this issue we take here the approach of tailoring the algorithm which creates the PDM data that goes on the REU--first-order delta-sigma modulation--to be aware of and recover from these delays.
* To use DMA to pipe bytes directly to `$d402` at maximum speed, this method completely takes over the C64. All interrupts are shut off, the screen is blanked, and the only thing the C64 is doing is sending bytes off the cartridge into the SID chip in a loop.

### Technical Details

The `pdm.asm` code works as follows:

* We use the pulse waveform, but in a non-standard way. Internally, the SID generates pulse waves using a 24-bit phase accumulator that counts up at a speed set by the frequency register. The chip takes the top 12 bits of this counter (values 0–4095) and compares them to the 12-bit pulse width set in `$d402` and `$d403`. If those top 12 bits are less than the pulse width, the duty cycle is on; otherwise, it's off.
* We set the frequency register at `$d400`-`$d401` to 0. This means the phase accumulator never advances. 
* The phase accumulator is reset to 0 by flipping the TEST bit on `$d404` on and off again. Between this and setting the frequency to zero, this locks the phase accumulator at 0.
* The way the SID chip determines the pulse waveform is to compare its counter to the pulse width and check if it is greater or not. Since the counter is locked at 0, owing to our telling it the frequency is zero and resetting the counter to 0 to never be incremented, then this reduces to asking if the pulse width is equal to 0. Therefore the only two meaningful states of the PW register are zero or non-zero, corresponding to the binary PDM signal. Accordingly, streaming the PDM data directly into either `$d402` or `$d403` plays the sample.

### Ablation Tests

I ran these ablation tests (i.e. leaving out a step to make sure it was necessary) to give evidence that this above technical explanation of how the effect is being achieved on the SID is correct:

*Setting the frequency to a non-zero value breaks the demo.* Expected: in this case, it will pretty much *never* be in the duty cycle, which leads to silence.

*Not flipping the TEST bit on and off to initialize breaks the demo.* Expected: if we don't reset the SID's internal phase register to zero, it will likely (prob = 4095/4096) not be zero. If it is not zero, we expect silence.

*Turning the TEST bit on and leaving it on breaks the demo.* Expected: with the TEST bit on, Oscillator 1 isn't just stuck on the zero phase, but disabled. So we expect silence, which is what we get.

*Changing the audio file by replacing 0's with 2's breaks the demo.* Expected: this is because any two non-zero values are equivalent in our setup, since the SID's logic in this case is reduced to changing if 0 < PW. Whether PW is 1 or 255 or 4095 makes no difference, so long as it is not zero. Changing all bytes to non-zero is thus equivalent to setting them all to 1, or all to 0, for that matter.

*Changing the audio file by replacing the 1's with 255's makes no audible difference.* Expected: this is the same reasoning as before.

### Acknowledgement and Further Materials

Achieving digitized audio on the Commodore 64 requires tricking the SID chip into doing things it was never originally designed for. Relying on prior discoveries by the C64 demoscene and retro-coding community was essential. I call attention to:

* **"The C64 Digi" by Robin Harbron, Levente Harsfalvi, and Stephen Judd**  
  *(Published in C=Hacking Issue #20, April 2001)*  
  This article describes the SID's `TEST` bit and how it interacts with the `$d402` Pulse Width register. Resetting the oscillator to execute fast pulse-width modulation is foundational to the 1-bit PDM DAC trick used in this project.  
  [Read C=Hacking #20](http://www.ffd2.com/fridge/chacking/c=hacking20.txt)
* **Pex "Mahoney" Tufvesson & High-Fidelity SID Audio**  
  While this project uses a 1-bit PDM/PWM approach at 1MHz, see also the work of Pex Tufvesson. The "Mahoney DAC" method abuses the SID's analog filter and `$d418` volume register to output 8-bit, 44.1kHz audio, challenging the limits of emulators at the time.  
  [Read the "Musik Run/Stop" Technical Details PDF](https://livet.se/mahoney/c64-files/Musik_RunStop_Technical_Details_by_Pex_Mahoney_Tufvesson_v2.pdf) | [Mahoney's Homepage](https://www.livet.se/mahoney/)


## Instructions

The procedure (you can skip the first two lines if you already have an mp3) is:

```bash
pip install yt-dlp
yt-dlp -x --audio-format mp3 -o "bettedaviseyes.mp3" "https://www.youtube.com/watch?v=EPOIS5taqA8"
ffmpeg -i bettedaviseyes.mp3 -t 16.7 -ar 985248 -ac 1 -f u8 -c:a pcm_u8 1mhz.pcm8
python build_reu.py 1mhz.pcm8 -o pdm.reu
java -jar KickAss.jar pdm.asm
x64sc -reu -reusize 16384 -reuimage pdm.reu pdm.prg
```

Steps are explained below in more detail.

### Step 0. (Optional) Download mp3 from a youtube source

If you don't have one handy, we can grab an mp3 from youtube:

```bash
pip install yt-dlp
```

We can convert then via:

```bash
yt-dlp -x --audio-format mp3 -o "your_song.mp3" "https://www.youtube.com/watch?v=YOUR_VIDEO_ID"
```

or

```bash
yt-dlp -x --audio-format wav -o "downloaded_audio.wav" "https://www.youtube.com/watch?v=YOUR_VIDEO_ID"
```

### Step 1. Convert the mp3 to an intermediate 8-bit pcm format

Now we use the famed ffmpeg tool:

```bash
ffmpeg -i your_song.mp3 -t 16.7 -ar 985248 -ac 1 -f u8 -c:a pcm_u8 1mhz.pcm8
```

Here 16.7 is the length of the sample in seconds, while 985248 is the clock speed (in Hz) of a PAL C64 system. (NTSC C64 has a clock speed of 1.022727 MHz.)

### Step 2. Build REU image `build_reu.py` -- Converts PCM8 to PDM

Next we take our `1mhz.pcm8` file and convert it to the 16 MiB REU image used by the program.

```bash
python build_reu.py 1mhz.pcm8 -o pdm.reu
```

An REU image is literally just the bytes themselves, there's no special metadata. Thus `pdm.reu` is just a 16MiB file of bytes that are either 0 or 1. (Why not bitpacked? Because our REU DMA trick requires bytes to transfer to `$d402`. It's a terribly inefficient use of cartridge space, though. If it weren't for this, we could fit over two minutes of audio using this format.)

The script uses what is called a 1st-order 1-bit *delta-sigma modulator*. This is very intimidating name for a rather simple algorithm. It is a quantization algorithm turning a string of 8-bit values into 1-bit values by comparing to 128 (or some suitable median value), and sweeping quantization error forward (c.f. dithering algorithms for images; this is just a 1D version of Floyd-Steinberg). 

We have two versions. The first version is as just described:

```python
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

```

In the second version, we address the 15 Hz ticking sound. The problem with Version 1 is that it is not aware that playback is being delayed for 10 cycles after every 65536 cycle bank with `$d402` stuck at its last value. We can improve the situation by accounting for the 'stuck' portions of playback during the bank switching cycles. Roughly, the idea is to take a majority poll over the region covered by the delay, excise the section the delay covers, and sweep forward the error. It seems likely there are improvements possible. Refer to the code for precise details.

To hear the effect of this fix, you can compare the versions

```bash
python build_reu.py 1mhz.pcm8 -o version1.reu -v 1  # prominent 15 Hz ticking sound 
python build_reu.py 1mhz.pcm8 -o version2.reu -v 2  # ticking issue substantially improved
```

### Step 3. Compilation of assembler code

The assembly code is written in Kick Assembler, and the compilation instruction is:

```bash
java -jar KickAss.jar pdm.asm
```

This creates `pdm.prg`.


### Step 4. Playback on VICE emulator

To use the VICE emulator with a 16MiB REU, type:

```bash
x64sc -reu -reusize 16384 -reuimage pdm.reu pdm.prg
```
