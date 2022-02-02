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

#if 0
  struct MappingTable
  {
    double x;
    double y;
  };

#endif

#if 0
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
#endif

  int num_samples;
  double maximum_sample_value;

public:
//  erfMapping ()       //constructor 1 with no arguments
//  {
//    this->num_samples = 1;
//    this->lower_range = 0;
//    this->maximum_sample_value = 5;
//  }
  explicit erfMapping(int n)    //constructor 1 with one argument
  {
    this->num_samples = n;
    this->maximum_sample_value = 5;
  }
  erfMapping(int n, double u)    //constructor 2 with three argument
  {
    this->num_samples = n;
    this->maximum_sample_value = u;
  }

  inline int get_num_samples() const;
  inline void set_num_samples(int n);

  inline void set_maximum_sample_value(double v);

  inline void setup();
  inline double get_erf(double xp) const;

private:

};



END_NAMESPACE_STIR

#include "stir/numerics/erfMapping.inl"

#endif // ERFMAPPING_H
