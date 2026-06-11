"""
Created on Thu Oct  9 12:38:17 2025

Module for calculating emission factors and the RVP curve (Reid Vapor Pressure)
used in the quantification of evaporative emissions of Volatile Organic
Compounds (VOCs) at fuel stations.

Developed based on EPA studies.

Author: Marcos Perrude  
Date: October 9, 2025
"""

from scipy.optimize import curve_fit


# 3rd-order polynomial function used to fit the RVP curve as a function of
# the ethanol percentage in the fuel.
def func(x, a, b, c, d):
    """
    3rd-order polynomial function used to fit the
    Reid Vapor Pressure (RVP) curve as a function of ethanol percentage.

    Parameters
    ----------
    x : float
        Ethanol percentage in the fuel.
    a, b, c, d : float
        Coefficients of the 3rd-order polynomial.

    Returns
    -------
    float
        Fitted RVP value for the given ethanol percentage.
    """
    return a*x**3 + b*x**2 + c*x + d


def carRefuelingEF(tamb_list, ethanolPercentage , rvpCurve):
    """
    Calculates the hourly vehicle refueling emission factor
    as a function of ambient temperature and ethanol percentage
    in the fuel.

    Parameters
    ----------
    tamb_list : numpy.ndarray
        List of ambient temperatures (°C).
    ethanolPercentage : float
        Ethanol percentage in the fuel.
    rvpCurve : pandas.DataFrame
        RVP curve with columns 'ETHANOL' and 'RVP'.

    Returns
    -------
    EF_list : list of float
        Hourly refueling emission factors (mg/L).
    """
    
    # ethanolPercentage = 27
    popt, _ = curve_fit(func, rvpCurve['ETHANOL'], rvpCurve['RVP'])
    EF_list = []
    for tamb in tamb_list:

        # Convert temperature from Celsius to Fahrenheit
        tConv = tamb * (9/5) + 32

        # Extract RVP for the ethanol percentage of the fuel
        rvpVal = func(ethanolPercentage, *popt)

        # Calculation of fuel temperature leaving the pump (California study)
        # Source: https://www.epa.gov/sites/default/files/2020-11/documents/420r20012.pdf
        td = 20.30 + 0.81 * tConv

        # Temperature difference between the tank and the dispenser
        deltaT = 0.418 * td - 16.6

        # Automatic conversion to mg/L (EPA)
        EF = 264.2 * (-5.909 - 0.0949*deltaT + 0.084*td + 0.485*rvpVal)

        EF_list.append(EF)
    return EF_list


# RVP calculation as a function of fuel ethanol percentage
def rvp(ethanolPercentage, gasolineEmissionServiceEF ,rvpCurve):
    """
    Calculates the RVP correction factor as a function of the
    ethanol percentage in the fuel.

    Parameters
    ----------
    ethanolPercentage : float
        Ethanol percentage in the fuel.
    gasolineEmissionServiceEF : float
        Base emission factor for gasoline.
    rvpCurve : pandas.DataFrame
        Fitted RVP curve.

    Returns
    -------
    float
        Emission factor adjusted by RVP and normalized.
    """

    # Extract vapor pressure from the curve as a function of ethanol percentage
    popt, _ = curve_fit(func, rvpCurve['ETHANOL'], rvpCurve['RVP'])
    rvp_val = func(ethanolPercentage, *popt)

    # Vapor pressure adopted in the USA (~10%)
    rvpUsaGasoline = 9.965801227
    return gasolineEmissionServiceEF * (rvp_val / rvpUsaGasoline)  # Normalization
