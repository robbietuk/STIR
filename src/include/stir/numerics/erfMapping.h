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

#ifndef ERFMAPPING_H
#define ERFMAPPING_H

START_NAMESPACE_STIR


//! erfMapping is a class to save values of the erf function
class erfMapping
{
private:

  struct MappingTable
  {
    double x;
    double y;
  };

  double interpolate( const std::vector<MappingTable> &data, double MappingTable::*x, double MappingTable::*y, double xValue ) const
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

  int num_entries;
  double lower_range;
  double upper_range;
  std::vector<MappingTable> map;

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

  inline int get_num_entires() const;
  inline void set_num_entires(const int n);

  inline void set_range(double l, double u);

  inline void setup();
//  inline int get_size();
  inline double get_erf(double xp) const;

private:

};



END_NAMESPACE_STIR

#include "stir/numerics/erfMapping.inl"

#endif // ERFMAPPING_H
