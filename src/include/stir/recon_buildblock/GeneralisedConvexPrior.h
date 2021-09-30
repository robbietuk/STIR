//
//
/*
    Copyright (C) 2000- 2007, Hammersmith Imanet Ltd
    This file is part of STIR.

    SPDX-License-Identifier: Apache-2.0

    See STIR/LICENSE.txt for details
*/
/*!
  \file
  \ingroup priors
  \brief Declaration of class stir::GeneralisedPrior

  \author Kris Thielemans
  \author Sanida Mustafovic

*/

#ifndef __stir_recon_buildblock_GeneralisedConvexPrior_H__
#define __stir_recon_buildblock_GeneralisedConvexPrior_H__


#include "stir/RegisteredObject.h"
#include "stir/ParsingObject.h"

START_NAMESPACE_STIR

class Succeeded;

/*!
  \ingroup priors
  \brief
  A base class for 'generalised' priors, i.e. priors for which at least
  a 'gradient' is defined.

  This class exists to accomodate FilterRootPrior. Otherwise we could
  just live with Prior as a base class.
*/
template <typename DataT>

class GeneralisedConvexPrior

{
public:

//    GeneralisedConvexPrior();

//  inline GeneralisedConvexPrior()
//  {
//    int x = 1;
//  };

public:
    //! compute the value of the function
  /*! For derived classes where this doesn't make sense, it's recommended to return 0.
   */
  virtual void
  compute_Hessian(DataT& prior_Hessian_for_single_densel,
                  const BasicCoordinate<3,int>& coords,
                  const DataT& current_image_estimate) const = 0;




  int my_value = 1;

};

END_NAMESPACE_STIR

//#include "stir/recon_buildblock/GeneralisedPrior.inl"

#endif
