//
//
/*
    Copyright (C) 2002- 2009, Hammersmith Imanet Ltd
    This file is part of STIR.

    SPDX-License-Identifier: Apache-2.0

    See STIR/LICENSE.txt for details
*/
/*!
  \file
  \ingroup priors
  \brief  implementation of the stir::GeneralisedConvexPrior

  \author Robert Twyman
*/

#include "stir/recon_buildblock/GeneralisedConvexPrior.h"
//#include "stir/DiscretisedDensity.h"
//#include "stir/Succeeded.h"
#include "stir/modelling/ParametricDiscretisedDensity.h"
//#include "stir/modelling/KineticParameters.h"

START_NAMESPACE_STIR

//template <typename elemT>
//void
//GeneralisedConvexPrior<elemT>::
//actual_compute_Hessian(elemT& prior_Hessian_for_single_densel,
//                const BasicCoordinate<3,int>& coords,
//                const elemT& current_image_estimate) const
//{
//  assert(  prior_Hessian_for_single_densel.has_same_characteristics(current_image_estimate));
//  prior_Hessian_for_single_densel.fill(0);
//  if (this->penalisation_factor==0)
//  {
//    return;
//  }
//
//  this->check(current_image_estimate);
//
//  const DiscretisedDensityOnCartesianGrid<3,elemT>& current_image_cast =
//          dynamic_cast< const DiscretisedDensityOnCartesianGrid<3,elemT> &>(current_image_estimate);
//
//  DiscretisedDensityOnCartesianGrid<3,elemT>& prior_Hessian_for_single_densel_cast =
//          dynamic_cast<DiscretisedDensityOnCartesianGrid<3,elemT> &>(prior_Hessian_for_single_densel);
//
//  if (weights.get_length() ==0)
//  {
//    compute_weights(weights, current_image_cast.get_grid_spacing(), this->only_2D);
//  }
//
//
//  const bool do_kappa = !is_null_ptr(kappa_ptr);
//
//  if (do_kappa && kappa_ptr->has_same_characteristics(current_image_estimate))
//    error("QuadraticPrior: kappa image has not the same index range as the reconstructed image\n");
//
//  const int z = coords[1];
//  const int y = coords[2];
//  const int x = coords[3];
//  const int min_dz = max(weights.get_min_index(), prior_Hessian_for_single_densel.get_min_index()-z);
//  const int max_dz = min(weights.get_max_index(), prior_Hessian_for_single_densel.get_max_index()-z);
//
//  const int min_dy = max(weights[0].get_min_index(), prior_Hessian_for_single_densel[z].get_min_index()-y);
//  const int max_dy = min(weights[0].get_max_index(), prior_Hessian_for_single_densel[z].get_max_index()-y);
//
//  const int min_dx = max(weights[0][0].get_min_index(), prior_Hessian_for_single_densel[z][y].get_min_index()-x);
//  const int max_dx = min(weights[0][0].get_max_index(), prior_Hessian_for_single_densel[z][y].get_max_index()-x);
//
//  elemT diagonal = 0;
//  for (int dz=min_dz;dz<=max_dz;++dz)
//    for (int dy=min_dy;dy<=max_dy;++dy)
//      for (int dx=min_dx;dx<=max_dx;++dx)
//      {
//        elemT current = 0.0;
//        if (dz == 0 && dy == 0 && dx == 0)
//        {
//          // The j == k case (diagonal Hessian element), which is a sum over the neighbourhood.
//          for (int ddz=min_dz;ddz<=max_dz;++ddz)
//            for (int ddy=min_dy;ddy<=max_dy;++ddy)
//              for (int ddx=min_dx;ddx<=max_dx;++ddx)
//              {
//                elemT diagonal_current = weights[ddz][ddy][ddx] *
//                                         derivative_20(current_image_estimate[z][y][x],
//                                                       current_image_estimate[z + ddz][y + ddy][x + ddx]);
//                if (do_kappa)
//                  diagonal_current *= (*kappa_ptr)[z][y][x] * (*kappa_ptr)[z+ddz][y+ddy][x+ddx];
//                current += diagonal_current;
//              }
//        }
//        else
//        {
//          // The j != k vases (off-diagonal Hessian elements)
//          current = weights[dz][dy][dx] * derivative_11(current_image_estimate[z][y][x],
//                                                        current_image_estimate[z + dz][y + dy][x + dx]);
//          if (do_kappa)
//            current *= (*kappa_ptr)[z][y][x] * (*kappa_ptr)[z+dz][y+dy][x+dx];
//        }
//        prior_Hessian_for_single_densel_cast[z+dz][y+dy][x+dx] = + current*this->penalisation_factor;
//      }
//}


#  ifdef _MSC_VER
    // prevent warning message on instantiation of abstract class
#  pragma warning(disable:4661)
#  endif

    template class GeneralisedConvexPrior<DiscretisedDensity<3,float> >;
    template class GeneralisedConvexPrior<ParametricVoxelsOnCartesianGrid >;

END_NAMESPACE_STIR
