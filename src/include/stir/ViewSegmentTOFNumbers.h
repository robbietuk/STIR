//
//
/*!
  \file
  \ingroup projdata

  \brief Definition of class stir::ViewSegmentTOFNumbers

  \author Kris Thielemans
  \author Sanida Mustafovic
  \author PARAPET project
  
*/
/*
    Copyright (C) 2000 PARAPET partners
    Copyright (C) 2000- 2009, Hammersmith Imanet Ltd
    This file is part of STIR.

    This file is free software; you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as published by
    the Free Software Foundation; either version 2.1 of the License, or
    (at your option) any later version.

    This file is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Lesser General Public License for more details.

    See STIR/LICENSE.txt for details
*/



#ifndef __stir_ViewSegmentNumbers_h__
#define __stir_ViewSegmentNumbers_h__

#include "stir/common.h"

START_NAMESPACE_STIR

/*!
  \brief A very simple class to store view and segment numbers 
  \ingroup projdata 
*/
class ViewSegmentTOFNumbers
{
public:

  //! an empty constructor (sets everything to 0)
  inline  ViewSegmentTOFNumbers();
  //! constructor taking view, segment and tof number as arguments
  inline ViewSegmentTOFNumbers( const int view_num, const int segment_num, const int tof_num=0);

  //! get segment number for const objects
  inline int segment_num() const;
  //! get view number for const objects
  inline int view_num() const;
  //! get tof number for const objects
  inline int tof_pos_num() const;

  //! get reference to segment number
  inline int&  segment_num();
  //! get reference to view number
  inline int&  view_num();
  //! get reference to timing position index
  inline int& tof_pos_num();

 
  //! comparison operator, only useful for sorting
  /*! order : (0,1) < (0,-1) < (1,1) ...*/
  inline bool operator<(const ViewSegmentTOFNumbers& other) const;

  //! test for equality
  inline bool operator==(const ViewSegmentTOFNumbers& other) const;
  inline bool operator!=(const ViewSegmentTOFNumbers& other) const;

private:
  int segment;
  int view;
  int tof;

};

END_NAMESPACE_STIR

#include "stir/ViewSegmentNumbers.inl"

#endif