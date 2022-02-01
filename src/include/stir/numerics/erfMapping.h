/*
    Copyright (C) 2022, UCL
    This file is part of STIR.

    SPDX-License-Identifier: Apache-2.0

    See STIR/LICENSE.txt for details
*/
/*!
  \file
  \ingroup erfMapping
  \brief Implementation of a erf mapping

  \author Robert Twyman
*/

//#include "stir/modulo.h"
//#include "stir/common.h"
//#include "stir/numerics/erf.h"
#include <map>


#ifndef ERFMAPPING_H
#define ERFMAPPING_H

START_NAMESPACE_STIR


struct MappingTable
{
  double x;
  double y;
};



double interpolate( const std::vector<MappingTable> &data, double MappingTable::*x, double MappingTable::*y, double xValue )
{
  auto ip = lower_bound( data.begin(), data.end(), xValue, [ x ]( MappingTable a, double b ){ return a.*x < b; } );

  // No extrapolation beyond data limits
  if ( ip == data.end  () )
  {
    return data.back ().*y;
  }
  else if ( ip == data.begin() )
  {
    return data.front().*y;
  }

  // Otherwise, linear interpolation
  auto im = ip - 1;
  double slope = ( (*ip).*y - (*im).*y ) / ( (*ip).*x - (*im).*x );      // dY/dX
  return (*im).*y + slope * ( xValue - (*im).*x );                       // Y0 + (dY/dX) * ( X - X0 )
}

//! erfMapping is a class to save values of the erf function
class erfMapping
{
private:
  int num_entries;
  double lower_range;
  double upper_range;
  std::vector<MappingTable> map;

  int closest_values[2];

public:
  erfMapping ()       //constructor 1 with no arguments
  {
    this->num_entries = 1;
    this->lower_range = 0;
    this->upper_range = 5;
  }
  erfMapping(int n)    //constructor 2 with one argument
  {
    this->num_entries = n;
    this->lower_range = 0;
    this->upper_range = 5;
  }
  erfMapping(int n, double l, double u)    //constructor 3 with three argument
  {
    this->num_entries = n;
    this->lower_range = l;
    this->upper_range = u;
  }

  int get_num_entires(){return this->num_entries;}
  void set_range(double l, double u);

  void setup();
  int get_size();
  double get_erf(const double xp);

private:

};



void
erfMapping::
setup()
{
  map.clear();
  MappingTable entry;
  double interval = (upper_range - lower_range) / get_num_entires();
  for (double x = lower_range; x <= upper_range; x = x + interval)
  {
    entry.x = x;
    entry.y = erf(x);
    map.push_back(entry);
  }
}





void
erfMapping::set_range(double l, double u)
{
  this->lower_range = l;
  this->upper_range = u;
}

int
erfMapping::get_size()
{
  return this->map.size();
}

double
erfMapping::get_erf(const double xp)
{
  return interpolate(this->map, &MappingTable::x, &MappingTable::y, xp);
}



END_NAMESPACE_STIR

#endif // ERFMAPPING_H