

#include "stir/numerics/BSplines1DRegularGrid.h"

START_NAMESPACE_STIR

inline void
erfMapping::
setup()
{
  this->_sampling_period = (this->maximum_sample_value) / this->get_num_samples();
  std::vector<double> erf_values;

  //Compute a vector of erf values
  for (int i=0; i<this->get_num_samples() ; ++i)
    erf_values.push_back(erf(i * this->_sampling_period));

  // Setup BSplines
  BSpline::BSplines1DRegularGrid<double, double> spline(erf_values, BSpline::linear);
  this->spline = spline;
//  this->_is_setup = true;
}

inline double
erfMapping::get_erf(double xp) const
{
  // BSplines cannot handle cases when (xp > 2*maximum_sample_value-4)
  // Assume erf(xp) = 1 or -1

  if (xp > this->maximum_sample_value)
    return 1.0;

  else if (xp < -this->maximum_sample_value)
    return -1.0;

  // erf() is odd and erf(0) = 0
  // Use erf(x) = -erf(-x) for increased sampling
  if (xp >= 0.0)
  {
    return this->spline.BSplines(xp / this->_sampling_period);
  }
  else
  {
    return -this->spline.BSplines(-xp / this->_sampling_period);
  }
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
