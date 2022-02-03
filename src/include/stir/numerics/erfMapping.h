
/*!
  \file
  \ingroup erfMapping
  \brief Implementation of an erf interpolation

  \author Robert Twyman
*/
/*
    Copyright (C) 2022, UCL
    This file is part of STIR.
    SPDX-License-Identifier: Apache-2.0
    See STIR/LICENSE.txt for details
*/

#include "stir/numerics/BSplines1DRegularGrid.h"

#ifndef ERFMAPPING_H
#define ERFMAPPING_H

START_NAMESPACE_STIR


/*! \ingroup numerics
   \name erfMapping
   \brief The class acts as a potentially faster way to compute many erf values by precomputing the function at
   regularly spaced intervals and using BSplines to interpolate a value.
*/
class erfMapping
{
private:

  //! The number of erf samples for the BSplines. [0 maximum_sample_value)
  int _num_samples = 1000;

  //! The sampling period, computed as \cmaximum_sample_value/\c_num_samples)
  double _sampling_period;

//  //! Used to check if setup has been run before parameter changes
//  bool _is_setup = false;

  //! BSplines object using linear interpolation
  BSpline::BSplines1DRegularGrid<double, double> spline;

  //! The maximum value x value of erf(x) we sample. Default erf(x=5) ~= 1
  double maximum_sample_value = 5;

public:

  erfMapping(){}

  explicit erfMapping(int num_samples)
  {
    this->_num_samples = num_samples;
  }

  //! Returns the number of erf samples
  inline int get_num_samples() const;
  //! Sets the number of erf samples
  inline void set_num_samples(int num_samples);

  //! Returns the maximum sample value
  inline int get_maximum_sample_value() const;
  //! Sets the maximum sample value
  inline void set_maximum_sample_value(double maximum_sample_value);

  /*! \brief Computes the erf() values and sets up BSplines */
  inline void setup();

/*! \brief Uses BSplines to interpolate the value of erf(xp)
 * If xp out of range (-\cmaximum_sample_value \cmaximum_sample_value) then outputs -1 or 1
 * @param xp input argument for erf(xp)
 * @return interpolated approximation of erf(xp)
 */
inline double get_erf(double xp) const;

};

END_NAMESPACE_STIR

#include "stir/numerics/erfMapping.inl"

#endif // ERFMAPPING_H
