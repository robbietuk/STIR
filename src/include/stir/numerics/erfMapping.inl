

#include "stir/numerics/BSplines1DRegularGrid.h"

START_NAMESPACE_STIR

inline void
erfMapping::
setup()
{
  this->_sampling_period = (2 * this->maximum_sample_value) / this->get_num_samples();
  std::vector<double> erf_values(this->get_num_samples() + 2);

  //Compute a vector of erf values
  for (int i=0; i<this->get_num_samples() + 2; ++i)
    erf_values[i] = erf(i * this->_sampling_period - this->maximum_sample_value);

  // Setup BSplines
  BSpline::BSplines1DRegularGrid<double, double> spline(erf_values, BSpline::linear);
  this->spline = spline;

  erf_values_vec = erf_values;
//  this->_is_setup = true;
}

inline double
erfMapping::get_erf_BSplines_interpolation(double xp) const
{
#if 1
    xp = std::clamp(xp,-this->maximum_sample_value, this->maximum_sample_value);
#else
  if (xp > this->maximum_sample_value)
    return 1.0;

  else if (xp < -this->maximum_sample_value)
    return -1.0;
#endif
  return this->spline.BSplines((xp + this->maximum_sample_value) / this->_sampling_period);
}


inline double
erfMapping::
get_erf_linear_interpolation(double xp) const
{
#if 1
    xp = std::clamp(xp,-this->maximum_sample_value, this->maximum_sample_value);
#else
  if (xp > this->maximum_sample_value)
    return 1.0;

  else if (xp < -this->maximum_sample_value)
    return -1.0;
#endif

  double my_point = ((xp + this->maximum_sample_value) / this->_sampling_period);
  int lower = static_cast<int>(floor(my_point));
  int upper = lower + 1;
  return erf_values_vec[lower] + (my_point - lower) * (erf_values_vec[upper] - erf_values_vec[lower]);
}

inline double
erfMapping::get_erf_nearest_neighbour_interpolation(double xp) const
{
#if 1
  xp = std::clamp(xp,-this->maximum_sample_value, this->maximum_sample_value);
#else
  if (xp > this->maximum_sample_value)
    return 1.0;

  else if (xp < -this->maximum_sample_value)
    return -1.0;
#endif
  // get_erf_BSplines_interpolation [nearest (ish)]
    return erf_values_vec[static_cast<int>((xp + this->maximum_sample_value) / this->_sampling_period)];
}

inline void
erfMapping::set_num_samples(const int num_samples)
{
  this->_num_samples = num_samples;
}

inline
int
erfMapping::get_num_samples() const
{
  return this->_num_samples;
}

int
erfMapping::get_maximum_sample_value() const
{
  return this->maximum_sample_value;
}

void
erfMapping::set_maximum_sample_value(double maximum_sample_value)
{
  this->maximum_sample_value = maximum_sample_value;
}

END_NAMESPACE_STIR
