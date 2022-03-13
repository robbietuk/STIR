/*!
  \file
  \ingroup projdata

  \brief inline implementations for class stir::ViewSegmentTOFNumbers

  \author Kris Thielemans
  \author Sanida Mustafovic
  \author PARAPET project
  

*/
/*
    Copyright (C) 2000 PARAPET partners
    Copyright (C) 2000- 2009, Hammersmith Imanet Ltd
    This file is part of STIR.

    SPDX-License-Identifier: Apache-2.0 AND License-ref-PARAPET-license

    See STIR/LICENSE.txt for details
*/


START_NAMESPACE_STIR

ViewSegmentTOFNumbers::
ViewSegmentTOFNumbers()
:segment(0), view(0), tof(0)
{}

ViewSegmentTOFNumbers::
ViewSegmentTOFNumbers(const int view_num, const int segment_num, const int tof_num)
:segment(segment_num), view(view_num), tof(tof_num)
{}

int
ViewSegmentTOFNumbers::segment_num() const
{
  return segment;}
int 
ViewSegmentTOFNumbers::view_num() const
{
  return view;}

int
ViewSegmentTOFNumbers::tof_pos_num() const
{
  return tof;}

int&
ViewSegmentTOFNumbers::segment_num()
{  return segment;}
int& 
ViewSegmentTOFNumbers::view_num()
{ return view;}

int&
ViewSegmentTOFNumbers::tof_pos_num()
{ return tof;}

bool 
ViewSegmentTOFNumbers::
operator<(const ViewSegmentTOFNumbers& other) const
{
  return (view< other.view) ||
    ((view == other.view) && (segment > other.segment));
}

bool 
ViewSegmentTOFNumbers::
operator==(const ViewSegmentTOFNumbers& other) const
{
  return (view == other.view) && (segment == other.segment) && (tof == other.tof);
}

bool 
ViewSegmentTOFNumbers::
operator!=(const ViewSegmentTOFNumbers& other) const
{
  return !(*this == other);
}
END_NAMESPACE_STIR
