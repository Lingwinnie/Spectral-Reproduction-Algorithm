import serial
import time
import os
import numpy as np
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt



#  PARAMETERS 
SERIAL_PORT = 'COM5'
TARGET_PATH = r" "
LIVE_FOLDER = r" "
EXTENSION = ".txt"

WL_MIN, WL_MAX = 350, 850
BAND_WIDTH = 20
INTERP_GRID = np.arange(WL_MIN, WL_MAX + 1, 1)
LED_WAVELENGTHS = [460, 525, 545, 591, 610, 630]
NB_LEDS = len(LED_WAVELENGTHS)
PWM_REF = 50

#  FUNCTIONS 
def read_spectrum(filepath):
    wavelengths, intensities = [], []
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 2:
                try:
                    wavelengths.append(float(parts[0]))
                    intensities.append(float(parts[1]))
                except ValueError:
                    continue
    return np.array(wavelengths), np.array(intensities)

def read_txt_spectrum(filepath):
    wavelengths, intensities = [], []
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        data_started = False
        for line in f:
            if not data_started:
                if line.strip().startswith("Wave") or line.strip().startswith("[nm]"):
                    data_started = True
                continue
            parts = line.strip().split(';')
            if len(parts) < 5:
                continue
            try:
                wl = float(parts[0].replace(',', '.'))
                inten = float(parts[4].replace(',', '.')) * 1  # µW/cm^2 → W/m^2
                wavelengths.append(wl)
                intensities.append(inten)
            except ValueError:
                continue
    return np.array(wavelengths), np.array(intensities)

def filter_spectrum(wl, inten):
    mask = (wl >= WL_MIN) & (wl <= WL_MAX)
    return wl[mask], inten[mask]

def interpolate_spectrum(wl, inten):
    f = interp1d(wl, inten, kind='linear', bounds_error=False, fill_value=0)
    return f(INTERP_GRID)

def decompose_into_bands(interpolated):
    bands = []
    for start in range(WL_MIN, WL_MAX, BAND_WIDTH):
        end = start + BAND_WIDTH
        mask = (INTERP_GRID >= start) & (INTERP_GRID < end)
        bands.append(np.max(interpolated[mask]) if np.any(mask) else 0)
    return np.array(bands)

def find_latest_file(folder, extension):
    files = [f for f in os.listdir(folder) if f.endswith(extension)]
    if not files:
        return None
    files.sort(key=lambda x: os.path.getmtime(os.path.join(folder, x)), reverse=True)
    return os.path.join(folder, files[0])

def set_led_pwm(ser, pwm_values):
    for i, pwm in enumerate(pwm_values):
        cmd = f"L{i+1}:{pwm}"
        ser.write((cmd + "\n").encode())
        time.sleep(0.05)

def get_measured_spectrum():
    for _ in range(10):
        file = find_latest_file(LIVE_FOLDER, EXTENSION)
        if file:
            wl, inten = read_txt_spectrum(file)
            if len(inten) > 0:
                return filter_spectrum(wl, inten)
        time.sleep(2)
    raise RuntimeError("Aucun spectre mesuré trouvé.")

#  TARGET SPECTRUM ANALYSIS 
print("reading target spectrum ...")
wl_target, inten_target = read_spectrum(TARGET_PATH)
wl_target, inten_target = filter_spectrum(wl_target, inten_target)
interp_target = interpolate_spectrum(wl_target, inten_target)
band_heights = decompose_into_bands(interp_target)
ref_band_idx = np.argmax(band_heights)
band_targets = band_heights / band_heights[ref_band_idx]

# LED-band ASSIGNMENT
led_band_map = {}
for i, led_wl in enumerate(LED_WAVELENGTHS):
    band_idx = int((led_wl - WL_MIN) // BAND_WIDTH)
    if 0 <= band_idx < len(band_targets):
        led_band_map[i] = band_idx

ref_led = min(led_band_map, key=lambda i: abs(led_band_map[i] - ref_band_idx))

print("--- Target spectrum Analysis summary ---")
print(f" Reference LED : LED {ref_led+1} ({LED_WAVELENGTHS[ref_led]} nm) in band {led_band_map[ref_led]}")
for idx in sorted(set(led_band_map.values())):
    print(f"Band {idx} : Relative height = {band_targets[idx]:.3f}")

#  ALLUMAGE LED RÉFÉRENCE 
print("Connection to Arduino...")
ser = serial.Serial(SERIAL_PORT, 9600, timeout=1)
time.sleep(2)

pwm_values = [0] * NB_LEDS
pwm_values[ref_led] = PWM_REF
set_led_pwm(ser, pwm_values)

time.sleep(3)

wl_meas, inten_meas = get_measured_spectrum()
interp_meas = interpolate_spectrum(wl_meas, inten_meas)
bands_measured = decompose_into_bands(interp_meas)
ref_intensity = bands_measured[led_band_map[ref_led]]

print("\n--- Raw intensities expected for each secondary band ---")
for i, b_idx in led_band_map.items():
    if i == ref_led:
        continue
    target = band_targets[b_idx] * ref_intensity
    print(f"LED {i+1} (band {b_idx}) : Raw intensity wanted = {target:.3e} µW/cm^2")


#  OPTIMIZATION SECONDARY LEDs 

print("\n=== Negligible secondary LEDs filtering ===")
usable_leds = []
ignored_leds = []

for i in range(NB_LEDS):
    if i == ref_led:
        continue
    band_idx = led_band_map.get(i, None)
    if band_idx is None:
        continue
    rel_height = band_targets[band_idx]
    if rel_height < 0.1:
        ignored_leds.append(i)
    else:
        usable_leds.append(i)

print(f"Ignored LEDs (band < 0.1) : {[i+1 for i in ignored_leds]}")
print(f"Preserved LEDs for optimisation : {[i+1 for i in usable_leds]}")
time.sleep(1.5)

#  REASSIGNMENT OF IGNORED LEDs IF HIGH PEAKS (> 0.2) 
print("\n=== Reassignment of ignored LEDs to other high bands ===")
assigned_bands = set(led_band_map.values())

for b_idx, rel_h in enumerate(band_targets):
    if rel_h > 0.2 and b_idx not in assigned_bands:
        candidates = [
            (abs(LED_WAVELENGTHS[i] - (WL_MIN + b_idx * BAND_WIDTH + BAND_WIDTH/2)), i)
            for i in ignored_leds
        ]
        if not candidates:
            continue
        _, best_led = min(candidates, key=lambda x: x[0])
        led_band_map[best_led] = b_idx
        assigned_bands.add(b_idx)
        ignored_leds.remove(best_led)
        usable_leds.append(best_led)
        print(f"  Band {b_idx} (h={rel_h:.2f}) reassigned to LED {best_led+1} ({LED_WAVELENGTHS[best_led]} nm)")
reassigned_leds = usable_leds.copy()

#  OPTIMIZATION PERSEVERED SECONDARY LEDs 
print("\n=== Optimisation secondary LEDs ===")

MIN_STEP      = 10
MAX_PWM       = 255
INITIAL_STEP  = 50
step          = INITIAL_STEP

MIN_RANGE = 10 

for i in usable_leds:
    low, high = 0, MAX_PWM
    best = 0

    print(f"\n-- Optimise LED {i+1} (band {led_band_map[i]}) --")

    fixed_pwms = pwm_values.copy()

    while high - low > MIN_RANGE:
        mid = (low + high) // 2
        fixed_pwms[i] = mid

        set_led_pwm(ser, fixed_pwms)
        time.sleep(3)
        wl_m, inten_m = get_measured_spectrum()
        bands = decompose_into_bands(interpolate_spectrum(wl_m, inten_m))

        if i in reassigned_leds:
            wl_idx = int(LED_WAVELENGTHS[i] - WL_MIN)
            measured = interpolate_spectrum(wl_m, inten_m)[wl_idx]
        else:
            measured = bands[led_band_map[i]]

        target   = band_targets[led_band_map[i]] * ref_intensity
        err      = measured - target

        print(f" LED {i+1} PWM={mid:3d} → measured={measured:.3e}, target={target:.3e}, err={'+' if err>0 else ''}{err:.3e}")

        if err < 0:
            low = mid
        else:
            high = mid

        best = mid

    pwm_values[i] = (low + high) // 2
    print(f" → LED {i+1} optimum ≈ {pwm_values[i]}")

print("\n=== Finals optimized PWM ===")
for idx, pwm in enumerate(pwm_values):
    print(f" LED {idx+1} : PWM = {pwm}")
set_led_pwm(ser, pwm_values)

ser.close()




#  FINAL ACQUISITION FOR VISUAL COMPARISON 
print("\nFinal acquisition for visual comparison")
time.sleep(3)
wl_final, inten_final = get_measured_spectrum()
wl_final, inten_final = filter_spectrum(wl_final, inten_final)
interp_final = interpolate_spectrum(wl_final, inten_final)

interp_final = np.clip(interp_final, 0, None)
interp_target = np.clip(interp_target, 0, None)

interp_target_norm = interp_target / np.max(interp_target)
interp_final_norm = interp_final / np.max(interp_final)

#  PLOT 
plt.figure(figsize=(10, 6))
plt.plot(INTERP_GRID, interp_target_norm, label='Reference Spectrum (Normalized)', color='blue', linewidth=2)
plt.plot(INTERP_GRID, interp_final_norm, label='Experimental Spectrum (Normalized)', color='red', linestyle='--', linewidth=2)

plt.title('Normalized Spectral Comparison')
plt.xlabel('Wavelength (nm)')
plt.ylabel('Relative Spectral Irradiance (UA)')
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()





