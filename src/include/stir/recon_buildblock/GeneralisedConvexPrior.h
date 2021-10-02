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
  \brief Declaration of class stir::GeneralisedConvexPrior

  \author Robert Twyman

*/

#ifndef __stir_recon_buildblock_GeneralisedConvexPrior_H__
#define __stir_recon_buildblock_GeneralisedConvexPrior_H__


#include "stir/recon_buildblock/GeneralisedPrior.h"

START_NAMESPACE_STIR

class Succeeded;

/*!
  \ingroup priors
  \brief
  Make a brief
*/
template <typename DataT>

class GeneralisedConvexPrior:
        virtual public GeneralisedPrior<DataT>

{
private:
  typedef GeneralisedPrior<DataT> base_type;

public:
    //! This computes a single row of the Hessian
    /*! The method computes a row (i.e. at a densel/voxel, indicated by \c coords) of the Hessian at \c current_estimate.
        Note that a row corresponds to an object of `DataT`.
        The method (as implemented in derived classes) should store the result in \c prior_Hessian_for_single_densel.
     */
  virtual void
  compute_Hessian(DataT& prior_Hessian_for_single_densel,
                  const BasicCoordinate<3,int>& coords,
                  const DataT& current_image_estimate) const = 0;

//    float penalisation_factor;




//  virtual void
//  actual_compute_Hessian(DataT& prior_Hessian_for_single_densel,
//                         const BasicCoordinate<3,int>& coords,
//                         const DataT& current_image_estimate) const;

  int my_value = 1;

};

END_NAMESPACE_STIR

//#include "stir/recon_buildblock/GeneralisedPrior.inl"

#endif
