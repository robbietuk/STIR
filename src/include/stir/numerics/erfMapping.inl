

#include "erfMapping.h"

START_NAMESPACE_STIR






inline void
erfMapping::
setup()
{
  std::vector<double> vec;
  double interval = (maximum_sample_value) / get_num_samples();
  for (auto x = 0.0; x <= maximum_sample_value; x = x + interval)
  {
    vec.push_back(erf(x));
  }
  // TODO: Add BSplines
}


inline void
erfMapping::set_maximum_sample_value(double v)
{
  this->maximum_sample_value = v;
}

inline double
erfMapping::get_erf(double xp) const
{
#if 0
//  return interpolate(this->map, &MappingTable::x, &MappingTable::y, xp);
#endif
  assert(xp <= maximum_sample_value);


  //TODO Rescale xp [0, max_sample) to [0,num_samples)

  // erf() is odd and erf(0) = 0
  // Use erf(x) = -erf(-x) for increased sampling
  if (xp >= 0.0)
  {
    //return erf(xp)
  }
  else
  {
    //return -erf(-xp)
  }
  return 0.0; //TODO Complete this
}

inline void
erfMapping::set_num_samples(const int n)
{
  this->num_samples = n;
}


inline
int
erfMapping::get_num_samples() const
{
  return this->num_samples;
}

END_NAMESPACE_STIR
