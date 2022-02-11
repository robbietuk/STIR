
/*!
  \file
  \ingroup FastErf
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
   \name FastErf
   \brief The class acts as a potentially faster way to compute many erf values by precomputing the function at
   regularly spaced intervals. [BSplines, linear, nearest neighbour] interpolation methods are available.
   Note, nearest neighbour is fastest and BSplines slowest method.
*/
class FastErf
{
private:

  //! The number of erf samples to take from -\cmaximum_sample_value to \cmaximum_sample_value
  int _num_samples = 1000;

  //! The sampling period, computed as \cmaximum_sample_value / \c_num_samples)
  double _sampling_period;

//  //! Used to check if setup has been run before parameter changes
//  bool _is_setup = false;

  //! BSplines object using linear interpolation
  BSpline::BSplines1DRegularGrid<double, double> spline;

  /*! The upper bound value x value of erf(x) used in sampling. Default erf(x=5) ~= 1.
   * The negative \cmaximum_sample_value is used as the lower bound.
   */
  double maximum_sample_value = 5;

  //! a vector/list of stored erf values
  std::vector<double> erf_values_vec;

public:
  FastErf(){}

  explicit FastErf(int num_samples)
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

  /*! \brief Computes the erf() values, sets up BSplines and sets up interpolation vectors.  */
  inline void set_up();

/*! \brief Uses BSplines to interpolate the value of erf(xp)
 * If xp out of range (-\cmaximum_sample_value \cmaximum_sample_value) then outputs -1 or 1
 * @param xp input argument for erf(xp)
 * @return interpolated approximation of erf(xp)
 */
inline double get_erf_BSplines_interpolation(double xp) const;

/*! \brief Uses linear interpolation of precomputed erf(x) values for erf(xp)
 * @param xp input argument for erf(xp)
 * @return linear interpolated approximation of erf(xp)
 */
inline double get_erf_linear_interpolation(double xp) const;

/*! \brief Uses nearest neighbour interpolation of precomputed erf(x) values for erf(xp)
 * @param xp input argument for erf(xp)
 * @return nearest neighbour interpolated approximation of erf(xp)
 */
inline double get_erf_nearest_neighbour_interpolation(double xp) const;

};

END_NAMESPACE_STIR

#include "stir/numerics/FastErf.inl"

#endif // ERFMAPPING_H
