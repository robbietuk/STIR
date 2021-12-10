# Author: Robert Twyman
# Copyright 2021 UCL
# This file is part of STIR.
# SPDX-License-Identifier: Apache-2.0
# See STIR/LICENSE.txt for details
# This python script can be converted easily into an iPython file by typing `p2j plot_GE_singles_info.py` into a command line.
# # Script for plotting and investigating GE singles information
# This script can be used to investigate the accuracy of the STIR `construct_randoms_from_GEsingles` utility
# by comparing its output with the measured data.
# In addition, it plots if the singles decay as expected (as this is assumed by `randoms_from_singles`).

import os
import sys
import numpy as np
import matplotlib.pyplot as plt

# # Core Functions

# Functions to convert between lambda and half-life

def get_lambda(half_life):
    return np.log(2) / half_life

def get_half_life(lbda):
    return np.log(2) / lbda

# Linear and decay functions

def linear_function(m, x, c):
    return m * x + c

def decay_function(lbda, x, S0):
    return S0 * np.exp(-lbda * x)

def get_lines_from_file(filename):
    print(f"Loading lines from file: \n  {filename}")
    with open(filename) as f:
        lines = f.readlines()
    return lines

def extract_singles_values_array_from_lines(lines):
    """
    This is a poorly written function that loops over each of the lines of the log file.
    The function filters the lines, looking for array depth information, given by "{" and "}".
    There are a few lines begining with "(" or "Time frame" or are empty that are ignored.
    """
    print("\nExtracting singles values array from lines...")
    line_num = 0
    num_lines = len(lines)
    singles_values = [[]]
    i = 0
    for l in lines:
        line_num += 1
        if line_num % 100 == 0:
            print(f"  Processing {line_num}/{num_lines} ({round(line_num / num_lines * 1000) / 10}%) lines...",
                  end="\r") # funky way to give percentages with decimal, e.g. 12.3%

        # Remove unneeded lines
        if len(l) <= 1 or l.startswith("(") or l.startswith("Time frame"):
            continue
            
        if l.count("{") == 2:
            # Increasing list depth
            i += 1
            singles_values.append([])
            
        if l.startswith(", "):
            # first 2 characters of the line are ", ", which we remove here.
            l = l[2::] 
            
        # remove any "{", "}", "\n" and split the remaining string into a list by "," as the delimiter.
        # Do not edit the original l
        tmp = l.replace("{", "").replace("}", "").replace("\n", "").split(",")
        
        
        if len(tmp) > 1:
            # Expect a list of some length, otherwise it may be an empty, which is discarded here.
            tmp = [float(i) for i in tmp] # Convert strings into float values.
            singles_values[i].append(tmp) 
            
    print(f"  Processed {line_num}/{num_lines} lines.")
    print("Converting to array...\n")
    return np.array(singles_values) # Ideally this whole function uses arrays rather than lists, this conversion is expensive.

# # Main script

# This next line is the main argument for the script. This should be a GE list mode file. 
# For development, I have hard coded this line.

lm_file = "/Users/roberttwyman/bin/Experiments/Phantoms/GE_data/OriginalFiles/torso-phantom-DMI3ring-RDF9/list/LIST0000.blfun"

# Output the print_GE_singles_values into a log file. No need to rerun once it has been run once.

log_file = "print_GE_singles_values.log"
if not os.path.isfile(log_file):
    print(f"Running print_GE_singles_values command! Saving into {log_file}")
    os.system(f"print_GE_singles_values {lm_file} > {log_file}")
else:
    print(f"{log_file} already exists.")

# Load the log file in text and imediately load into a function to extract the lines into an array

singles_values = extract_singles_values_array_from_lines(get_lines_from_file(log_file))

seconds = np.array([i for i in range(len(singles_values))]) # Assume each array corresponds to one second

# for i in range(len(singles_values)):
# singles_per_second[i] = np.sum(singles_values[i])

singles_per_second = np.array([np.sum(singles_values[i]) for i in range(len(singles_values))])

print(seconds)

# Take the natural log of the decay function gives a linear function 
# `log( S0 exp(-2lambda t) = log(S0) -2lambda t )`. 
# Fit the data in `singles_per_second` to a linear function and compute `lbda` (lambda) and `S0`

lbda, S0 = np.polyfit(seconds, np.log(singles_per_second), 1)
lbda = -lbda
S0 = np.exp(S0)
measured_half_life = get_half_life(lbda) # Convert lbda into half-life
exponential_fit = [decay_function(lbda, t, S0) for t in seconds]

# The first line of this print is a sanity check, expect value to be close to 1.

print(f"sum(singles_per_second) / sum(exponential_fit) = {np.sum(singles_per_second) / np.sum(exponential_fit)}\n",
      f"measured half life from polyfit = {measured_half_life} seconds")

# Compute expected behaviour based upon F18 half-life and compare the difference in the number of singles.

F18_half_life = 6586.2
F18_lbda = get_lambda(F18_half_life)
F18_singles = [decay_function(F18_lbda, t, S0) for t in seconds]
print(f"sum(F18_singles) / sum(exponential_fit) = {np.sum(F18_singles) / np.sum(exponential_fit)}\n",
      f"F18_half_life = {F18_half_life} seconds.")

# Plot the singles rates here.

plt.figure()
plt.plot(singles_per_second)
plt.plot(exponential_fit)
plt.plot(F18_singles)
plt.title("Number of Singles plotted over time")
plt.legend(["GE singles per second", 
            "Exponential fit to GE singles per second", 
            "F18 decay"])
plt.ylabel("Single Events per second")
plt.xlabel("Seconds (s)")
plt.ylim(bottom=0, top=6.5e6)
plt.show()

print(f"sum(singles_per_second) / sum(exponential_fit) = {np.sum(singles_per_second) / np.sum(exponential_fit)}\n",
      f"sum(F18_singles) / sum(exponential_fit) = {np.sum(F18_singles) / np.sum(exponential_fit)}\n",
      f"measured half_life = {measured_half_life}\n\n"
      f"F18_half_life = {F18_half_life}")

# # Discussion of decay investigation results
# The above fit and plot indicates that the singles are sensitive to an alternative cause than just radioactive decay, as indicaed by the measured half-life being greater than the F18 value. 
# An explaination for this may be detector deadtime. If this is the case we need to reconsider the plot.
# At low singles rate the impact due to deadtime would be insignificant, therefore we would expect the `GE singles per second` and the `Exponential fit` plots to intersect. _N.B. This intersection would likely not appear on the range of this figure._ It is expected that the measured `S0` would be too small in this case as the current value is influnced by deadtime.

# # Sum over alternative axis of `singles_values`

# The following is a little additional investigation conducted. Sum over each of the time interval to give the sum for each detector-ring pair over time.

plt.figure()
plt.imshow(np.sum(singles_values, axis=0))
plt.title("Sum of singles for each Detector and Ring in the scanner.")
plt.xlabel("Detector Number")
plt.ylabel("Ring Number")
plt.show()

# Sum over each time intervals and the rings. Flip the vector to see structure. 

plt.figure()
plt.plot(np.sum(singles_values, axis=(0,1)))
plt.plot(np.flip(np.sum(singles_values, axis=(0,1))))
plt.xlabel("Detector Number")
plt.ylabel("Number of singles")
plt.show()

# Sum over the time intervals and the detectors. Flip to see structure.

plt.figure()
plt.plot(np.sum(singles_values, axis=(0,2)))
plt.plot(np.flip(np.sum(singles_values, axis=(0,2))))
plt.xlabel("Rings Number")
plt.ylabel("Number of singles")
plt.show()

# # A general conclusion
# We see the expected sinusoidal behaviour over the detectors but in the rings we may observe higher activity at one axial extremity due to activity of the source.

# # 1. New Investigation Into `randoms_from_singles`
# We are told that the following applies for randoms from singles
# $r_{x,y} = (2\tau)s_{x}s_{y}$,
# where $r_{x,y}$ is the rate of random coincidence production between detectors $x$ and $y$, $s_{x}$ and $s_{y}$ are the single event rates in the respective detectors, and $(2\tau)$ is the width of the coincidence window [C. Stearns, 2003]. Yet the singles rate is not constant over the aquisition (mostly related to radioactive decay and consequental effects (e.g. deadtime, block busy and radiokinetic changes)) and therefore we need to correct for this. We implement the following correction factor ($CF$):
# $CF = \frac{\lambda T_{acq}}{2} \frac{1-exp(-2\lambda T_{acq})}{(1-exp(-\lambda T_{acq}))^2}, \quad (1)$
# where $\lambda$ is the decay constant of the isotope. There are also notes regarding if $CF$ is small (i.e. $CF < 1
# \%$ for $\lambda T_{acq} = \ln(2)/2$, where  $ T_{acq}=\tau_{1/2}/2$, half the the radioisotope half-life).
# Some important equations (some are present above):
# 1. Decay constant: $\lambda =\ln(2)/\tau_{1/2}, \quad (2)$ 
# 2. Isotope halflife: $\tau_{1/2} = \ln(2)/\lambda, \quad (3)$
# 3. Decay equation: $A(t) = A(0) exp(-\lambda t), \quad (4)$
# Do not confused $\tau_{1/2}$ (isotope half-life) with $(2\tau)$ (width of the coincidence window). 
# N.B. It was the $-2\lambda$ implementation in the $CF$ computation that caused previous issues in STIR, see https://github.com/UCL/STIR/pull/960, which was corrected for [here](https://github.com/UCL/STIR/pull/961/files#diff-1dce22df0a557f2fa7e570c64a452c06e82e4dbe5d1f3a452f831341025d0c6bL79).

# # 2. Evaluation of STIR implementation
# In STIR, we use the `decay_correction_factor(isotope_halflife, start_time, endtime)` function in the `randoms_from_singles` code. 
# `2.1 decay_correction_factor`
# ====
# The `decay_correction_factor` has two implementations. We are interested in the aforemented. The documentation states that we are computing the following integral:
# $\frac{(t_2-t_1)}{ \int_{t_1}^{t_2} \! 2^{-t/\tau_{1/2}} \, dt} =^? \frac{\lambda (t_{2} - t_{1})}{exp(-\lambda t_{1}) - exp(-\lambda t_{2})}$,
# where `start_time`=$t_1$ and `end_time`=$t_2$ and `isotope_halflife`=$\tau_{1/2}$. Is this functions implementation correct?
# Solving:
# $\frac{(t_2-t_1)}{ \int_{t_1}^{t_2} \! 2^{-t/\tau_{1/2}} \, dt}$
# 1. Subsituting $\tau_{1/2} = \ln(2)/\lambda$
# $... = \frac{(t_2-t_1)}{ \int_{t_1}^{t_2} \! 2^{\frac{-t \lambda}{\ln(2)}} \, dt} $
# 2. Integrating
# $... = \frac{\lambda(t_2-t_1)}{ exp(-\lambda t_1( - exp(-\lambda t_2)} $
# This function is correct in terms of implmentation and documentation of the integral. N.B. There is also another usage of the function here if $|\lambda*(t_2-t_1))| < .01$, where $|\cdot|$ applies an absolute opterator, then the function returns $exp(\lambda t_1)$, which is something I am not checking here.

# 2.2 Usage in `randoms_from_singles`
# ====
# 2.2.1 `randoms_from_singles`: Mathmatical validation:
# ---
# The previous shows that the function is correct but are we using it correctly. We can rewrite (1), assuming general radioactive decay (4), as:
# $r_{i,j} = (2\tau) s_{i}(0)s_{j}(0) exp(-2\lambda t), \quad (5)$
# where $s_{i}(0)$ and $s_{j}(0)$ are the singles rate of $i$ and $j$ (respectively) at time $t=0$ but the earliest time that the singles were measured. Again remember we are simple assuming standard radioactive decay of the source, an assumption that will be discussed later. Note, $t=0$ is not the same as $t_1$. Integrating over time, between $t_1$ and $t_2$ to compute the total singles for each bin:
# $R_{i,j} = \int_{t_1}^{t_2} (2\tau) s_{i}(0)s_{j}(0) exp(-2\lambda t) dt, \quad (6)$
# Furthermore, we can assume the singles rate ($s_i(t) = s_i(0) exp(-\lambda t)$) decays as per (4). Reordering this for $s_i(0)$ gives
# $s_i(0) = \frac{s_i(t)}{exp(-\lambda t)}, \quad (7)$
# Substituting this into (6):
# $R_{i,j} = \int_{t_1}^{t_2} (2\tau) s_i(t)s_j(t) \frac{exp(-2\lambda t)}{exp(-\lambda t)^2} dt, \quad (8)$
# Evidently $\int_{t_1}^{t_2} s_i(t) dt$ is the sum of all singles over the period between $t_1$ and $t_2$, notated as $S_i$ and $S_j$ respectively. Hence,
# $R_{i,j} = (2\tau) S_i S_j \frac{\int_{t_1}^{t_2} exp(-2\lambda t) dt}{\big( \int_{t_1}^{t_2} exp(-\lambda t) dt \big)^2}, \quad (9)$
# and solve the integrals:
# $R_{i,j} = (2\tau) S_i S_j \frac{\lambda \big( exp(-2\lambda t_1) - exp(-2\lambda t_2) \big)}{\big(exp(-\lambda t_1) - exp(-\lambda t_2)\big)^2}, \quad (10)$


# 2.2.2 `randoms_from_singles`: Code validation:
# ---
# The function is given as follows
# `void randoms_from_singles(ProjData& proj_data, const SinglesRates& singles, const float coincidence_time_window, float isotope_halflife)`
# - `proj_data` is filled as the randoms estimate 
# - `singles` are provided (i.e. `GE::RDF_HDF5::SinglesRatesFromGEHDF5  singles(input_filename)` in `construct_randoms_from_GEsingles` and we assume this is correct 
# - `coincidence_time_window` 
# - `isotope_halflife`.is provided as a scalar value
# The `total_singles` is an array populated by getting singles value between $t_1$ and $t_2$ for each combination in `num_rings` and `num_detectors_per_ring`. This is assumed to be correct.
# Proceeding to the decay correction of the singles rates.
# The STIR code implementation reads as: 
# ```
# 1.    const double duration = frame_defs.get_duration(1);
# 2.    const double decay_corr_factor = decay_correction_factor(isotope_halflife, 0., duration);
# 3.    const double double_decay_corr_factor = decay_correction_factor(0.5*isotope_halflife, 0., duration);
# 4.    const double corr_factor = square(decay_corr_factor) / double_decay_corr_factor / duration;
# ```
# which mathmatically is written as :
# 1. Compupte $\Delta t = t_2 - t_1$
# 2.`decay_corr_factor`$
# = \frac{(t_2-t_1)}{ \int_{t_1}^{t_2} \! 2^{-t/\tau_{1/2}} \, dt} 
# = \frac{\lambda(t_2-t_1)}{ exp(-\lambda t_1) - exp(-\lambda t_2)}
# $
# 3. `double_decay_corr_factor` $
# = \frac{(t_2-t_1)}{ \int_{t_1}^{t_2} \! 2^{-t/(0.5\tau_{1/2})} \, dt}
# = \frac{2\lambda(t_2-t_1)}{ exp(-2\lambda t_1) - exp(-2\lambda t_2)}
# $
# 4. `corr_factor` $
# = (t_2-t_1)^{-1}\frac{
# \big(\frac{\lambda(t_2-t_1)}{ exp(-\lambda t_1) - exp(-\lambda t_2)}\big)^2
# }{
# \big(\frac{2\lambda(t_2-t_1)}{ exp(-2\lambda t_1) - exp(-2\lambda t_2)}\big)
# }
# = \frac{\lambda }{2} 
# \frac{
# exp(-2\lambda t_1) - exp(-2\lambda t_2)
# }{
# \big( exp(-\lambda t_1) - exp(-\lambda t_2) \big)^2
# }, \quad (11)
# $
# (11) is noticably comparable to (10)

# 2.2.3 Remaining questions and comments...
# ---
# Discuss the standard decay assumption.
# Question: Why not perform frequent samples the sum of singles over time frames $\Delta t $ that are short, perform numerical integration, and disregard the explictit integration. This will help with problems such as deadtime correction and [the scanner background activity issue](https://github.com/UCL/STIR/issues/959).
# - Follow up: How do you deal with $\Delta t \approx (2\tau)$. Will cause problems with noise?
# How important is the issue with $\tau_{1/2}$ we observed above?
# - Since it is only a global scale factor we can figure this from the summation of the randoms count from `construct_randoms_from_GEsingles`
# - Modify3 $\tau_{1/2} = 1,000s (\Delta T = 3600s)$ : Data sum: 2.88578e+08
# - STIR master ($\tau_{1/2} = 6586.2s$): Data sum: 1.98391e+08
# - Modify $\tau_{1/2} = 7914.9s$ (observed $\tau_{1/2}$): Data sum: 1.97673e+08
# - Modify2 $\tau_{1/2} = 1,000,000,000,000s$ (1 tillion second): Data sum: 1.96052e+08

