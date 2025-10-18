# Spectral-Reproduction-Algorithm
Python implementation of a spectral reproduction algorithm using LEDs. 

## Context
This code has been developed as part of a project aimed at better regulating and standardizing artificial lighting conditions indoors.
The objective is being able to reproduce any type of light spectrum (on condition that the user has the desired LEDs) automatically and with a desired precision.

## Requirements
- Avasoft (full) for spectrometer acquisition.  
- Spectrometer compatible with Avasoft.  
- Arduino board with PWM outputs and LEDs wired to PWM pins.  
- Arduino IDE (to upload Arduino sketch).  
- Python (Anaconda recommended) with `pyserial`, NumPy, SciPy, Matplotlib, Jupyter (optional).  
- Folder for live Avasoft output (ASCII .txt).

## Quick hardware & acquisition checklist
1. Wire each LED to a separate Arduino PWM output pin.  
2. Upload the Arduino firmware (provided sketch) using Arduino IDE. Close the IDE Serial Monitor before running the Python control program.  
3. In Avasoft: set *Absolute Irradiance*, *continuous measurements*.  
   - In *Spectrum → File → Live output → To file*: Add output folder, check *ASCII* (.txt).  
   - Set measurement interval (must be ≥ integration time). Set *Nr scans = 0* for continuous acquisition.  
   - Save dark file and start acquisition. If files are not auto-saved, go to *Options → Save Spectra Periodically* and enable auto-save.  

## Program workflow (methodology)
1. **Read target spectrum** and **live experimental spectra** saved by Avasoft (for SpectraWiz for other uses).  
   - The code uses `read_txt_spectrum` for Avasoft output and `read_spectrum` for SpectraWiz. 

2. **Split the target spectrum into bands.**
   - Each band is defined around its local maximum (highest point).

3. **Normalize** the target spectrum to its highest band peak.  
   - From that normalization the code computes **relative heights** for each band (values in [0, 1]).

4. **Assign LEDs to bands** using LED emission wavelengths (user-provided list in PWM output order).  
   - The code only attempts to reproduce bands that are assigned to an LED.

5. **Negligible-band rule:** if a band assigned to a LED has relative height < 0.1 (adjustable), it is treated as noise and ignored.  
   - You can change this threshold in the code (see configuration / line ~150).

6. **Reassignment rule for unassigned bands:**  
   - If a band without an assigned LED has height > 0.2 (adjustable), the program looks for the nearest LED.  
   - If that nearest LED was originally classed negligible, it gets reassigned to this band; otherwise the band stays ignored.  
   - Threshold for reassignment can be changed in the code (see configuration / line ~170).
7. **Reference LED and scaling:**  
   - The LED corresponding to the highest band becomes the **reference LED**. The program sets the reference LED PWM to a user-chosen value (default = **50**, adjustable).  
   - It turns on the reference LED, acquires the experimental spectrum, then computes the raw PWM values required for the other LEDs to reach the target relative heights (based on measured reference intensity).

8. **Iterative refinement:**  
   - For each secondary LED, the program tests, measures error (sign = “-” if exp < target; “+” if exp > target), and refines the PWM step until a chosen convergence criterion is met.

9. **Result visualization:** once matching is achieved, the program plots target vs. reproduced spectrum normalized on the same graph for comparison. 

## Initialization 
- **Serial port**: set the correct Arduino serial port in the script.  
- **Paths**:
  - Path to the **target spectrum** file.  
  - Path to the **Avasoft live output** folder (where .txt files are saved).  
- **Spectra reading function**: choose `read_txt_spectrum` (Avasoft) or `read_spectrum` (SpectraWiz or any other soft that uses ".IRR" or similar files) according to your acquisition software.  
- **Working spectral window**: set the wavelength range the code will consider.  
- **Band width**: the width around each peak used to define a band.  
- **LED emission wavelengths**: provide a list of LED center wavelengths **in the same order** as the Arduino PWM outputs.  
- **Reference LED PWM**: pick initial PWM for reference LED (default 50) — choose carefully: if reference LED is too weak relative to required bands, reproduction will fail.  
- **Relative height thresholds**: the two thresholds described above (negligible and reassignment) are configurable in the script (see indicated line numbers).

## Recommended parameter values
- Start with **ref PWM = 50**. If some bands never reach target, increase ref PWM or use a stronger LED for that band.  
- Default negligible threshold = 0.1 ; reassignment threshold = 0.2 .
- Ensure integration time and saved file interval in Avasoft are compatible (interval ≥ integration time).  
- Close Arduino Serial Monitor while Python controls the Arduino serial port.

## Output
- A figure plotting **normalized target** vs **normalized reproduced** spectrum for visual comparison.  
- Optionally saved PWM settings and numerical error metrics.

## Troubleshooting (quick)
- No file read: check Avasoft live output folder and ASCII option.  
- Arduino not responding: close Serial Monitor; verify COM port.  
- Bands never reach target: check LED emission wavelengths order, increase PWM, or change reference LED.  
- If non-assigned band > threshold but closest LED is usable, the band remains ignored — reduce thresholds only if justified.

## Author 
Lingwinnie — Master of Nanosciences and Nanotechnologies : Nanoscale and Quantum Engineering

## License
MIT 
