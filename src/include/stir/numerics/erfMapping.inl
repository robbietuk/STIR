

#include "erfMapping.h"

START_NAMESPACE_STIR






inline void
erfMapping::
setup()
{
  map.clear();
  MappingTable entry{};
  double interval = (upper_range - lower_range) / get_num_entires();
  for (double x = lower_range; x <= upper_range; x = x + interval)
  {
    entry.x = x;
    entry.y = erf(x);
    map.push_back(entry);
  }
}


inline void
erfMapping::set_range(double l, double u)
{
  this->lower_range = l;
  this->upper_range = u;
}

//inline
//int
//erfMapping::get_size()
//{
//  return this->map.size();
//}

inline double
erfMapping::get_erf(double xp) const
{
  return interpolate(this->map, &MappingTable::x, &MappingTable::y, xp);
}

inline void
erfMapping::set_num_entires(const int n)
{
  this->num_entries = n;
}


inline
int
erfMapping::get_num_entires() const
{
  return this->num_entries;
}

END_NAMESPACE_STIR
