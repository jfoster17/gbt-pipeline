"""Module containing all the calibration methods for the GBT Pipeline.

This includes both Position-switched and Frequency-switched calibration.

"""
# Copyright (C) 2007 Associated Universities, Inc. Washington DC, USA.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
# Correspondence concerning GBT software should be addressed as follows:
#       GBT Operations
#       National Radio Astronomy Observatory
#       P. O. Box 2
#       Green Bank, WV 24944-0002 USA

# $Id$

import numpy as np
import math
import smoothing
from Pipeutils import Pipeutils


class Calibration(object):
    """Class containing all the calibration methods for the GBT Pipeline.

    This includes both Position-switched and Frequency-switched calibration.

    """

    def __init__(self):

        # set calibration constants
        self.BB = .0132  # Ruze equation parameter
        self.UNDER_2GHZ_TAU_0 = 0.008
        self.SMOOTHING_WINDOW = 3
        self.pu = Pipeutils()

    # ------------- Unit methods: do not depend on any other pipeline methods

    def total_power(self, cal_on, cal_off, t_on, t_off):
        return np.ma.mean((cal_on, cal_off), axis=0), t_on+t_off

    def tsky_correction(self, tsky_sig, tsky_ref, spillover):
        return spillover*(tsky_sig-tsky_ref)

    def aperture_efficiency(self, reference_eta_a, freq_hz):
        """Determine aperture efficiency

        Keyword attributes:
        freq_hz -- input frequency in Hz

        Returns:
        eta -- point or main beam efficiency (range 0 to 1)

        EtaA model is from memo by Jim Condon, provided by Ron Maddalena

        >>> cal = Calibration()
        >>> round(cal.aperture_efficiency(.71, 23e9), 6)
        0.647483
        >>> round(cal.aperture_efficiency(.91, 23e9), 6)
        0.829872

        """

        freq_ghz = float(freq_hz)/1e9
        return reference_eta_a * math.e**-((self.BB * freq_ghz)**2)

    def main_beam_efficiency(self, reference_eta_b, freq_hz):
        """Determine main beam efficiency, given reference etaB value and freq.

        This is the same equation as is used to determine aperture efficiency.
        The only difference is the reference value.

        """

        return self.aperture_efficiency(reference_eta_b, freq_hz)

    def elevation_adjusted_opacity(self, zenith_opacity, elevation):
        """Compute elevation-corrected opacities.

        Keywords:

        zenith_opacity -- opacity based only on time
        elevation -- (float) elevation angle of integration or scan

        """
        number_of_atmospheres = self._natm(elevation)

        corrected_opacity = zenith_opacity * number_of_atmospheres

        return corrected_opacity

    def _natm(self, el_deg):
        """Compute number of atmospheres at elevation (deg)

        Keyword arguments:
        el_deg -- input elevation in degrees

        Returns:
        n_atmos -- output number of atmospheres

        Estimate the number of atmospheres along the line of site
        at an input elevation

        This comes from a model reported by Ron Maddale

        1) A = 1/sin(elev) is a good approximation down to about 15 deg but
        starts to get pretty poor below that.  Here's a quick-to-calculate,
        better approximation that I determined from multiple years worth of
        weather data and which is good down to elev = 1 deg:

        if (elev LT 39):
        A = -0.023437  + 1.0140 / math.sin( (math.pi/180.)*(elev + 5.1774 /
            (elev + 3.3543) ) )
        else:
        A = math.sin(math.pi*elev/180.)

        natm model is provided by Ron Maddalena

        """

        degree = math.pi/180.

        if (el_deg < 39.):
            first_term = -0.023437
            denominator = math.sin(degree*(el_deg + 5.1774/(el_deg + 3.3543)))
            second_term = 1.0140 / denominator
            n_atmos = first_term + second_term
        else:
            n_atmos = math.sin(degree*el_deg)

        #print('Model Number of Atmospheres:', n_atmos,
        #      ' at elevation ', el_deg)
        return n_atmos

    def _tatm(self, freq_hz, tmp_c):
        """Estimates the atmospheric effective temperature

        Keyword arguments:
        freq_hz -- input frequency in Hz
        where: tmp_c     - input ground temperature in Celsius

        Returns:
        air_temp_k -- output Air Temperature in Kelvin

        Based on local ground temperature measurements.  These estimates
        come from a model reported by Ron Maddalena

        1) A = 1/sin(elev) is a good approximation down to about 15 deg but
        starts to get pretty poor below that.  Here's a quick-to-calculate,
        better approximation that I determined from multiple years worth of
        weather data and which is good down to elev = 1 deg:

            if (elev LT 39) then begin
                A = -0.023437  + 1.0140 / sin( (!pi/180.)
                     * (elev + 5.1774 / (elev + 3.3543) ) )
            else begin
                A = sin(!pi*elev/180.)
            endif

        2) Using Tatm = 270 is too rough an approximation since Tatm can vary
        from 244 to 290, depending upon the weather conditions and observing
        frequency.  One can derive an approximation for the default Tatm that
        is accurate to about 3.5 K from the equation:

        TATM = (A0 + A1*FREQ + A2*FREQ^2 +A3*FREQ^3 + A4*FREQ^4 + A5*FREQ^5)
                    + (B0 + B1*FREQ + B2*FREQ^2 + B3*FREQ^3 + B4*FREQ^4 +
        B5*FREQ^5)*TMPC

        where TMPC = ground-level air temperature in C and Freq is in GHz.  The
        A and B coefficients are:

                                    A0=    259.69185966 +/- 0.117749542
                                    A1=     -1.66599001 +/- 0.0313805607
                                    A2=     0.226962192 +/- 0.00289457549
                                    A3=   -0.0100909636 +/- 0.00011905765
                                    A4=   0.00018402955 +/- 0.00000223708
                                    A5=  -0.00000119516 +/- 0.00000001564
                                    B0=      0.42557717 +/- 0.0078863791
                                    B1=     0.033932476 +/- 0.00210078949
                                    B2=    0.0002579834 +/- 0.00019368682
                                    B3=  -0.00006539032 +/- 0.00000796362
                                    B4=   0.00000157104 +/- 0.00000014959
                                    B5=  -0.00000001182 +/- 0.00000000105


        tatm model is provided by Ron Maddalena

        >>> cal = Calibration()
        >>> round(cal._tatm(23e9, 40), 6)
        298.885174
        >>> round(cal._tatm(23e9, 30), 6)
        289.780603
        >>> round(cal._tatm(1.42e9, 30), 6)
        271.978666

        """

        # where TMPC = ground-level air temperature in C and Freq is in GHz.
        # The A and B coefficients are:
        aaa = [259.69185966, -1.66599001, 0.226962192,
               -0.0100909636,  0.00018402955, -0.00000119516]
        bbb = [0.42557717,    0.033932476, 0.0002579834,
               -0.00006539032, 0.00000157104, -0.00000001182]
        freq_ghz = float(freq_hz)/1e9
        freq = float(freq_ghz)
        freq2 = freq*freq
        freq3 = freq2*freq
        freq4 = freq3*freq
        freq5 = freq4*freq

        air_temp_k = (aaa[0] + aaa[1]*freq + aaa[2]*freq2 + aaa[3]*freq3
                      + aaa[4]*freq4 + aaa[5]*freq5)
        air_temp_k = (air_temp_k +
                      (bbb[0] + bbb[1]*freq + bbb[2]*freq2
                       + bbb[3]*freq3 + bbb[4]*freq4 + bbb[5]*freq5)
                      * float(tmp_c))

        return air_temp_k

    def zenith_opacity(self, coeffs, freq_ghz):
        """Interpolate low and high opacities across a vector of frequencies

        Keywords:
        coeffs -- (list) opacitiy coefficients from archived text file,
                    produced by GBT weather prediction code
        freq_ghz -- frequency value in GHz

        Returns:
        A zenith opacity at requested frequency.

        """
        # interpolate between the coefficients based on time for a
        # given frequency
        def _interpolated_zenith_opacity(freq):
            # for frequencies < 2 GHz, return a default zenith opacity
            if np.array(freq).mean() < 2:
                result = np.ones(np.array(freq).shape)*self.UNDER_2GHZ_TAU_0
                return result
            result = 0
            for idx, term in enumerate(coeffs):
                if idx > 0:
                    result = result + term*freq**idx
                else:
                    result = term
            return result

        zenith_opacity = _interpolated_zenith_opacity(freq_ghz)
        return zenith_opacity

    def tsys(self, tcal, cal_on, cal_off):
        nchan = len(cal_off)
        low = int(.1*nchan)
        high = int(.9*nchan)
        cal_off = (cal_off[low:high]).mean()
        cal_on = (cal_on[low:high]).mean()
        return np.float(tcal*(cal_off/(cal_on-cal_off))+tcal/2)

    def antenna_temp(self, tsys, sig, ref, t_sig, t_ref):
        ref_smoothed = smoothing.boxcar(ref, self.SMOOTHING_WINDOW)
        ref_smoothed = self.pu.masked_array(ref_smoothed)

        spectrum = tsys * ((sig-ref_smoothed)/ref_smoothed)
        exposure_time = (t_sig * t_ref * self.SMOOTHING_WINDOW
                         / (t_sig + t_ref*self.SMOOTHING_WINDOW))
        return spectrum, exposure_time

    def _ta_fs_one_state(self, sigref_state, sigid, refid):

        sig = sigref_state[sigid]['TP']

        ref = sigref_state[refid]['TP']
        ref_cal_on = sigref_state[refid]['cal_on']
        ref_cal_off = sigref_state[refid]['cal_off']

        tcal = ref_cal_off['TCAL']

        tsys = self.tsys(tcal,  ref_cal_on['DATA'],  ref_cal_off['DATA'])

        a_temp_params = {'tsys': tsys, 'sig': sig, 'ref': ref,
                         't_sig': sigref_state[sigid]['EXPOSURE'],
                         't_ref': sigref_state[refid]['EXPOSURE']}
        antenna_temp, exposure = self.antenna_temp(**a_temp_params)

        return antenna_temp, tsys, exposure

    def ta_fs(self, sigref_state):

        ta0, tsys0, exposure0 = self._ta_fs_one_state(sigref_state, 0, 1)
        ta1, tsys1, exposure1 = self._ta_fs_one_state(sigref_state, 1, 0)

        # shift in frequency
        sig_centerfreq = sigref_state[0]['cal_off']['OBSFREQ']
        ref_centerfreq = sigref_state[1]['cal_off']['OBSFREQ']

        sig_delta = sigref_state[0]['cal_off']['CDELT1']
        channel_shift = -((sig_centerfreq-ref_centerfreq)/sig_delta)

        # do integer channel shift to second spectrum
        ta1_ishifted = np.roll(ta1, int(channel_shift))
        if channel_shift > 0:
            ta1_ishifted[:channel_shift] = float('nan')
        elif channel_shift < 0:
            ta1_ishifted[channel_shift:] = float('nan')

        # do fractional channel shift
        fractional_shift = channel_shift - int(channel_shift)
        #doMessage(logger, msg.DBG, 'Fractional channel shift is',
        #          fractional_shift)
        xxp = range(len(ta1_ishifted))
        yyp = ta1_ishifted
        xxx = xxp-fractional_shift

        yyy = np.interp(xxx, xxp, yyp)
        ta1_shifted = self.pu.masked_array(yyy)

        exposures = np.array([exposure0, exposure1])
        tsyss = np.array([tsys0, tsys1])
        tas = [ta0, ta1_shifted]

        # average shifted spectra
        ta = self.average_spectra(tas, tsyss, exposures)

        # average tsys
        tsys = self.average_tsys(tsyss, exposures)

        # only sum the exposure if frequency switch is "in band" (i.e.
        # overlapping channels); otherwise use the exposure from the
        # first state only
        if abs(channel_shift) < len(ta1):
            exposure_sum = exposure0 + exposure1
        else:
            exposure_sum = exposure0

        return ta, tsys, exposure_sum

    def ta_star(self, antenna_temp, beam_scaling, opacity, spillover):
        # opacity is corrected for elevation
        return antenna_temp*((beam_scaling*(math.e**opacity))/spillover)

    def jansky(self, ta_star, aperture_efficiency):
        return ta_star/(2.85*aperture_efficiency)

    def interpolate_by_time(self, reference1, reference2,
                            first_ref_timestamp, second_ref_timestamp,
                            integration_timestamp):

        time_btwn_ref_scans = second_ref_timestamp-first_ref_timestamp
        aa1 = ((second_ref_timestamp-integration_timestamp)
               / time_btwn_ref_scans)
        aa2 = (integration_timestamp-first_ref_timestamp) / time_btwn_ref_scans
        return aa1*reference1 + aa2*reference2

    def make_weights(self, tsyss, exposures):
        return exposures / tsyss**2

    def average_tsys(self, tsyss, exposures):
        weights = self.make_weights(tsyss, exposures)
        return np.sqrt(np.average(tsyss**2, axis=0, weights=weights))

    def average_spectra(self, specs, tsyss, exposures):
        weights = self.make_weights(tsyss, exposures)
        if float('nan') in specs[0] or float('nan') in specs[1]:
            weight0 = np.ma.array([weights[0]]*len(specs[0]),
                                  mask=specs[0].mask)
            weight1 = np.ma.array([weights[1]]*len(specs[1]),
                                  mask=specs[1].mask)
            weights = [weight0.filled(0), weight1.filled(0)]
        return np.ma.average(specs, axis=0, weights=weights)

    def getReferenceAverage(self, crefs, tsyss, exposures, timestamps,
                            tambients, elevations):

        # convert to numpy arrays
        crefs = np.array(crefs)
        tsyss = np.array(tsyss)
        exposures = np.array(exposures)
        timestamps = np.array(timestamps)
        tambients = np.array(tambients)
        elevations = np.array(elevations)

        avg_tsys = self.average_tsys(tsyss, exposures)

        avg_tsys80 = avg_tsys.mean(0)  # single value for mid 80% of band
        avg_cref = self.average_spectra(crefs, tsyss, exposures)
        exposure = np.sum(exposures)

        avg_timestamp = timestamps.mean()
        avg_tambient = tambients.mean()
        avg_elevation = elevations.mean()

        return (avg_cref, avg_tsys80, avg_timestamp, avg_tambient,
                avg_elevation, exposure)

    def tsky(self, ambient_temp_k, freq_hz, tau):
        """Determine the sky temperature contribution at a frequency

        Keywords:
        ambient_temp_k -- (float) mean ambient temperature value, in kelvin
        freq -- (float)
        tau -- (float) opacity value
        Returns:
        the sky model temperature contribution at frequncy channel

        """
        ambient_temp_c = ambient_temp_k-273.15  # convert to celcius
        airTemp = self._tatm(freq_hz, ambient_temp_c)

        tsky = airTemp * (1-math.e**(-tau))

        return tsky
