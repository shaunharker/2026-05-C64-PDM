.pc = $0801 "Basic Upstart"
:BasicUpstart(main)

.pc = $0810 "Main"

main:
    sei                        // I flag = 1 → CPU ignores IRQ line

    // ────────── CIA interrupt masking ──────────
    // $DC0D : CIA1 Interrupt Control Reg.   (Timer A/B, TOD, SDR, FLAG → IRQ)
    // $DD0D : CIA2 Interrupt Control Reg.   (same bits, but routed to NMI)
    //
    // When WRITING:  bit 7 = "set if 1, clear if 0" for the lower bits.
    // %01111111 ($7F)  →  clear bits 0..4 = disable every IRQ source.
    // When READING:  returns pending flags and CLEARS them.
    lda #$7f
    sta $dc0d                  // disable all CIA1 IRQ sources
    sta $dd0d                  // disable all CIA2 NMI sources
    lda $dc0d                  // ack/clear any pending CIA1 IRQ
    lda $dd0d                  // ack/clear any pending CIA2 NMI

    // ────────── CPU port banking ──────────
    // $01 : 6510 on-chip I/O port (data).  Bits 0..2 control PLA banking:
    //   bit 0 LORAM   : 1 = BASIC ROM at $A000..$BFFF
    //   bit 1 HIRAM   : 1 = KERNAL ROM at $E000..$FFFF
    //   bit 2 CHAREN  : 1 = I/O at $D000..$DFFF, 0 = character ROM there
    // $35 = %00110101 → LORAM=1? No: ROMs OFF, I/O ON, RAM at $A000/$E000.
    // (Standard "all-RAM with I/O" demo setup.)
    lda #$35
    sta $01

    // ────────── Disable VIC raster activity ──────────
    // $D011 : VIC Control Register 1
    //   bit 0..2  YSCROLL
    //   bit 3     RSEL (24/25 rows)
    //   bit 4     DEN  – Display ENable
    //   bit 5     BMM  – bitmap mode
    //   bit 6     ECM  – extended colour mode
    //   bit 7     RST8 – high bit of raster compare
    // Clearing DEN stops the VIC from triggering BAD LINES,
    // which would steal up to 43 cycles every 8 raster lines and
    // jitter our REU DMA rate.
    lda $d011
    and #$ef                   // clear bit 4 (DEN)
    sta $d011

    // ────────── SID setup (PW-modulated DAC) ──────────
    // $D418 : Volume + filter mode
    //   bits 0..3  master volume 0..15
    //   bit 4..6   LP / BP / HP filter routing
    //   bit 7      voice-3 mute
    lda #$0f
    sta $d418                  // full volume, filter bypassed

    // SID voice-1 registers:
    //   $D400/01  FREQ lo/hi   (16 bit)
    //   $D402/03  PW   lo/hi   (12 bit, upper nibble of $D403)
    //   $D404     control      (gate, sync, ring, test, waveform)
    //   $D405     attack duration/decay duration
    //   $D406     sustain volume/release duration



    lda #$00
    sta $d400                  // FREQ = 0  → oscillator never advances
    sta $d401
    sta $d403                  // PW high nibble = 0  (PW = 8 bits LSB only)
    sta $d405                  // A=0 D=0

    /*
    // ablation test #1: including these two lines would break code by making freq > 0
    lda #$01
    sta $d400
    */
    
    lda #$f0
    sta $d406                  // S=F R=0

    // $D404 control bits:
    //   bit0 gate, bit1 sync, bit2 ring, bit3 TEST,
    //   bit4 triangle, bit5 sawtooth, bit6 PULSE, bit7 noise

    // ablation test #2: leaving the next two lines out would break code
    //                   we need to toggle TEST bit to reset oscillator accumulator
    //                   if this is not done, then toggling PW between 0 and 1 is unlikely
    //                   to do anything with a halted oscillator accumulator
    lda #$49                   // %01001001 = pulse + TEST + gate
    sta $d404                  //   TEST forces oscillator accumulator to 0
    
    lda #$41                   // %01000001 = pulse + gate (clear TEST)
    sta $d404                  //   accumulator now held at 0 with freq=0
                               //   → audio output is the PW value itself.

    // ────────── REU (1764/1750) setup ──────────
    // $DF00  status   (read-only: INT pending, FAULT, SIZE, VERSION)
    // $DF01  command  bit7 EXECUTE   bit5 AUTOLOAD
    //                 bit4 NO-FF00   bits1..0 type
    //                 type: 00=stash(C64→REU) 01=fetch(REU→C64)
    //                       10=swap          11=verify
    // $DF02  C64 address LO
    // $DF03  C64 address HI
    // $DF04  REU address LO
    // $DF05  REU address HI
    // $DF06  REU bank
    // $DF07  length LO
    // $DF08  length HI   ($0000 = 65536 bytes)
    // $DF09  interrupt mask
    // $DF0A  address control
    //          bit6 = fix REU address
    //          bit7 = fix C64 address

    // C64 destination = $D402 (voice-1 PW low byte)
    lda #$02
    sta $df02
    lda #$d4
    sta $df03

    // Hold C64 address fixed at $D402; let REU address increment
    // through the sample stream.
    lda #%10000000
    sta $df0a

    // REU source starts at $0000 in the current bank.
    lda #$00
    sta $df04
    sta $df05

    // Length = $10000 (a whole bank per fetch).
    lda #$00
    sta $df07
    sta $df08

    lda #$00
    sta $d020                  // black border
    sta $d021                  // black background

    // ────────── Unrolled Playback loop ──────────
    // One REU fetch transfers ~64 KB at ~1 byte / cycle ≈ 1 MHz to $D402.
    // The CPU is HALTED while DMA runs; AUTOLOAD restores the start
    // address/length so each new bank starts at REU $0000.

    lda #$b1                   // %10110001 (execute, autoload, fetch)
    ldy #$00                   // Start at bank 0

    // Kick Assembler compile-time unrolling
    .for (var i = 0; i < 256; i++) {
        .if (i > 0) {
            iny                // 2 cycles (Skip incrementing on the very first bank)
        }
        sty $df06              // 4 cycles - pick bank Y
        sta $df01              // 4 cycles - GO (CPU halts here until 64KB xfer done)
    }

    lda #$02
    sta $d020                  // red border = "done"

hang:
    jmp hang
