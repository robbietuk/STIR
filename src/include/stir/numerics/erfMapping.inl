

#include "stir/numerics/BSplines1DRegularGrid.h"

START_NAMESPACE_STIR

inline void
erfMapping::
setup()
{
  this->_sampling_period = (this->maximum_sample_value) / this->get_num_samples();
  std::vector<double> erf_values(this->_num_samples);

  //Compute a vector of erf values
  for (int i=0; i<this->get_num_samples() ; ++i)
    erf_values[i] = erf(i * this->_sampling_period);

  // Setup BSplines
  BSpline::BSplines1DRegularGrid<double, double> spline(erf_values, BSpline::linear);
  this->spline = spline;

  erf_values_vec = erf_values;
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


inline double
erfMapping::get_erf_linear(double xp) const
{
  // get_erf [linear]



  if (xp > this->maximum_sample_value)
    return 1.0;

  else if (xp < -this->maximum_sample_value)
    return -1.0;

  // erf() is odd and erf(0) = 0
  // Use erf(x) = -erf(-x) for increased sampling
  if (xp >= 0.0)
  {
    double my_point = (xp / this->_sampling_period) - 1;
    int lower = static_cast<int>(floor(my_point));
    int upper = lower + 1;
    return erf_values_vec[lower] + (my_point - lower) *
                        (
                            (erf_values_vec[upper] - erf_values_vec[lower])
//                          / (upper - lower) // should equal 1
    );  }
  else
  {
    double my_point = (-xp / this->_sampling_period) - 1;
    int lower = static_cast<int>(floor(my_point));
    int upper = lower + 1;
    return -(erf_values_vec[lower] + (my_point - lower) *
                        (
                            (erf_values_vec[upper] - erf_values_vec[lower])
//                          / (upper - lower) // should equal 1
                        )  );
  }
}

inline double
erfMapping::get_erf_nn(double xp) const
{
  if (xp > this->maximum_sample_value)
    return 1.0;

  else if (xp < -this->maximum_sample_value)
    return -1.0;

  // get_erf [nearest (ish)]
  if (xp >= 0.0)
    {
      return erf_values_vec[static_cast<int>(xp / this->_sampling_period) - 1];
    }

  else {
    return -erf_values_vec[static_cast<int>(-xp / this->_sampling_period)];
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
