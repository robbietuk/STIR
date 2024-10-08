//
//
/*
    Copyright (C) 2003- 2005, Hammersmith Imanet Ltd
    This file is part of STIR.

    SPDX-License-Identifier: Apache-2.0

    See STIR/LICENSE.txt for details
*/

/*!
  \file
  \ingroup numerics
  \brief Implementation of the stir::norm(), stir::norm_squared() functions and
  stir::NormSquared unary function

  \author Kris Thielemans

*/

#include <functional>
#include <cmath>
#ifdef BOOST_NO_STDC_NAMESPACE
namespace std
{
using ::fabs;
}
#endif

START_NAMESPACE_STIR

template <typename T>
struct NormSquared<std::complex<T>>
{
  double operator()(const std::complex<T>& x) const { return square(x.real()) + square(x.imag()); }
};

template <class Iter>
double
norm_squared(Iter begin, Iter end)
{
  double res = 0;
  for (Iter iter = begin; iter != end; ++iter)
    res += norm_squared(*iter);
  return res;
}

template <class Iter>
double
norm(Iter begin, Iter end)
{
  return sqrt(norm_squared(begin, end));
}

template <class elemT>
inline double
norm(const Array<1, elemT>& v1)
{
  return norm(v1.begin(), v1.end());
}

template <class elemT>
inline double
norm_squared(const Array<1, elemT>& v1)
{
  return norm_squared(v1.begin(), v1.end());
}

END_NAMESPACE_STIR
