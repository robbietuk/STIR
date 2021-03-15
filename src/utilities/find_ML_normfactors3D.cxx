/*
 Copyright (C) 2001- 2008, Hammersmith Imanet Ltd
 Copyright (C) 2019-2020, University College London
 Copyright (C) 2016-2017, PETsys Electronics
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
/*!
 
 \file
 \ingroup utilities
 
 \brief Find normalisation factors using an ML approach
 
 \author Kris Thielemans
 \author Tahereh Niknejad
 */
#include "stir/ML_norm.h"

#include "stir/Scanner.h"
#include "stir/stream.h"
#include "stir/display.h"
#include "stir/CPUTimer.h"
#include "stir/utilities.h"
#include "stir/info.h"
#include "stir/error.h"
#include <boost/format.hpp>
#include <iostream>
#include <fstream>
#include <string>
#include <algorithm>
#include "stir/ProjData.h"
//#include "stir/ProjDataInterfile.h"

static void print_usage_and_exit(const std::string& program_name)
{
  std::cerr<<"Usage: " << program_name << " [--display | --print-KL | --include-bucket-timing-model] \\\n"
	   << " out_filename_prefix measured_data model num_iterations num_eff_iterations\n"
	   << " set num_iterations to 0 to do only efficiencies\n";
  exit(EXIT_FAILURE);
}


USING_NAMESPACE_STIR

int main(int argc, char **argv)
{
    const char * const program_name = argv[0];
    // skip program name
    --argc;
    ++argv;

  bool do_display = false;
  bool do_KL = false;
  bool do_geo = true;
  bool do_bucket = false;

  // first process command line options
  while (argc>0 && argv[0][0]=='-' && argc>=1)
    {
      if (strcmp(argv[0], "--display")==0)
	{
	  do_display = true;
	  --argc; ++argv;
	}
      else if (strcmp(argv[0], "--print-KL")==0)
	{
	  do_KL  = true;
	  --argc; ++argv;
	}
      else if (strcmp(argv[0], "--include-geometric-model")==0)
	{
	  do_geo = true;
	  --argc; ++argv;
	}
      else if (strcmp(argv[0], "--include-bucket-timing-model")==0)
	{
      do_bucket = true;
	  --argc; ++argv;
	}
      else
	print_usage_and_exit(program_name);
    }
  // go back to previous counts such that we don't have to change code below
  ++argc; --argv;
  
  //check_geo_data();
  if (argc!=6)
    {
      print_usage_and_exit(program_name);
    }
  const int num_eff_iterations = atoi(argv[5]);
  const int num_iterations = atoi(argv[4]);
  shared_ptr<ProjData> model_data = ProjData::read_from_file(argv[3]);
  shared_ptr<ProjData> measured_data = ProjData::read_from_file(argv[2]);
  const std::string out_filename_prefix = argv[1];
  const int num_rings = 
    measured_data->get_proj_data_info_sptr()->get_scanner_sptr()->
    get_num_rings();
  const int num_detectors_per_ring = 
    measured_data->get_proj_data_info_sptr()->get_scanner_sptr()->
    get_num_detectors_per_ring();
  const int num_transaxial_buckets =
          measured_data->get_proj_data_info_sptr()->get_scanner_sptr()->
                  get_num_transaxial_buckets();
  const int num_transaxial_blocks =
    measured_data->get_proj_data_info_sptr()->get_scanner_sptr()->
    get_num_transaxial_blocks();
  const int num_axial_buckets =
          measured_data->get_proj_data_info_sptr()->get_scanner_sptr()->
                  get_num_axial_buckets();
  const int num_axial_blocks =
    measured_data->get_proj_data_info_sptr()->get_scanner_sptr()->
    get_num_axial_blocks();
  const int num_transaxial_blocks_per_bucket =
          measured_data->get_proj_data_info_sptr()->get_scanner_sptr()->
          get_num_transaxial_blocks_per_bucket();
  const int num_axial_blocks_per_bucket =
          measured_data->get_proj_data_info_sptr()->get_scanner_sptr()->
                  get_num_axial_blocks_per_bucket();
    const int num_transaxial_crystals_per_block =
    measured_data->get_proj_data_info_sptr()->get_scanner_sptr()->
    get_num_transaxial_crystals_per_block();
    const int num_axial_crystals_per_block =
    measured_data->get_proj_data_info_sptr()->get_scanner_sptr()->
    get_num_axial_crystals_per_block();
    const int num_axial_crystals_per_bucket = num_axial_blocks_per_bucket * num_axial_crystals_per_block;
    const int num_transaxial_crystals_per_bucket = num_transaxial_blocks_per_bucket * num_transaxial_crystals_per_block;

    
    CPUTimer timer;
    timer.start();
    
    FanProjData model_fan_data;
    FanProjData fan_data;
    Array<2,float> data_fan_sums(IndexRange2D(num_rings, num_detectors_per_ring));
    DetectorEfficiencies efficiencies(IndexRange2D(num_rings, num_detectors_per_ring));
    
    GeoData3D measured_geo_data(num_axial_crystals_per_bucket, num_transaxial_crystals_per_bucket/2, num_rings, num_detectors_per_ring ); //inputes have to be modified
    GeoData3D norm_geo_data(num_axial_crystals_per_bucket, num_transaxial_crystals_per_bucket/2, num_rings, num_detectors_per_ring ); //inputes have to be modified
    
    BucketData3D measured_bucket_data(num_axial_buckets, num_transaxial_buckets, num_axial_buckets - 1, num_transaxial_buckets - 1);
    BucketData3D norm_bucket_data(num_axial_buckets, num_transaxial_buckets, num_axial_buckets - 1, num_transaxial_buckets - 1);


    make_fan_data(model_fan_data, *model_data);
    {
        // next could be local if KL is not computed below
        FanProjData measured_fan_data;
        float threshold_for_KL;
        // compute factors dependent on the data
        {
            make_fan_data(measured_fan_data, *measured_data);
    
/* TEMP FIX */
 for (int ra = model_fan_data.get_min_ra(); ra <= model_fan_data.get_max_ra(); ++ra)
    {
      for (int a = model_fan_data.get_min_a(); a <= model_fan_data.get_max_a(); ++a)
        {
          for (int rb = std::max(ra,model_fan_data.get_min_rb(ra)); rb <= model_fan_data.get_max_rb(ra); ++rb)
            {
              for (int b = model_fan_data.get_min_b(a); b <= model_fan_data.get_max_b(a); ++b)      
                if (model_fan_data(ra,a,rb,b) == 0)
                  measured_fan_data(ra,a,rb,b) = 0;
            }
        }
    }

           threshold_for_KL = measured_fan_data.find_max()/100000.F;
            //display(measured_fan_data, "measured data");
            
            make_fan_sum_data(data_fan_sums, measured_fan_data);
            make_geo_data(measured_geo_data, measured_fan_data);
            make_bucket_data(measured_bucket_data, measured_fan_data);
            if (do_display)
                display(measured_bucket_data, "raw bucket data from measurements");
            
           /* {
             char *out_filename = new char[20];
             sprintf(out_filename, "%s_%d.out",
             "fan", ax_pos_num);
             std::ofstream out(out_filename);
             out << data_fan_sums;
             delete[] out_filename;
             }
            */
        }
        
        //std::cerr << "model min " << model_fan_data.find_min() << " ,max " << model_fan_data.find_max() << std::endl;
        if (do_display)
            display(model_fan_data, "model");
#if 0
        {
            shared_ptr<ProjData> out_proj_data_ptr =
            new ProjDataInterfile(model_data->get_proj_data_info_sptr()->clone,
                                  output_file_name);
            
            set_fan_data(*out_proj_data_ptr, model_fan_data);
        }
#endif
        
        for (int iter_num = 1; iter_num<=std::max(num_iterations, 1); ++iter_num)
        {
            if (iter_num== 1)
            {
                efficiencies.fill(sqrt(data_fan_sums.sum()/model_fan_data.sum()));
                norm_geo_data.fill(1);
                norm_bucket_data.fill(1);
            }
            // efficiencies
            {
                fan_data = model_fan_data;
                apply_geo_norm(fan_data, norm_geo_data);
                apply_bucket_norm(fan_data, norm_bucket_data);
                if (do_display)
                    display(fan_data,  "model*geo*bucket");
                for (int eff_iter_num = 1; eff_iter_num<=num_eff_iterations; ++eff_iter_num)
                {
                    iterate_efficiencies(efficiencies, data_fan_sums, fan_data);
                    {
                        char *out_filename = new char[out_filename_prefix.size() + 30];
                        sprintf(out_filename, "%s_%s_%d_%d.out",
                                out_filename_prefix.c_str(), "eff", iter_num, eff_iter_num);
                        std::ofstream out(out_filename);
                        out << efficiencies;
                        delete[] out_filename;
                    }
                    if (do_KL)
                    {
                        apply_efficiencies(fan_data, efficiencies);
                        std::cerr << "measured*norm min " << measured_fan_data.find_min() << " ,max " << measured_fan_data.find_max() << std::endl;
                        std::cerr << "model*norm min " << fan_data.find_min() << " ,max " << fan_data.find_max() << std::endl;
                        if (do_display)
                            display( fan_data, "model_times_norm");
                        info(boost::format("KL %1%") % KL(measured_fan_data, fan_data, threshold_for_KL));
                        // now restore for further iterations
                        fan_data = model_fan_data;
                        apply_geo_norm(fan_data, norm_geo_data);
                      apply_bucket_norm(fan_data, norm_bucket_data);
                    }
                    if (do_display)
                    {
                        fan_data.fill(1);
                        apply_efficiencies(fan_data, efficiencies);
                        display(fan_data, "eff norm");
                        // now restore for further iterations
                        fan_data = model_fan_data;
                        apply_geo_norm(fan_data, norm_geo_data);
                      apply_bucket_norm(fan_data, norm_bucket_data);
                    }
                    
                }
            } // end efficiencies
            
            
            // geo norm
            
            fan_data = model_fan_data;
            apply_efficiencies(fan_data, efficiencies);
          apply_bucket_norm(fan_data, norm_bucket_data);
            
            if (do_geo)
              iterate_geo_norm(norm_geo_data, measured_geo_data, fan_data);
            
            #if 0

            { // check
                for (int a=0; a<measured_geo_data.get_length(); ++a)
                    for (int b=0; b<num_detectors; ++b)
                        if (norm_geo_data[a][b]==0 && measured_geo_data[a][b]!=0)
                            warning("norm geo 0 at a=%d b=%d measured value=%g\n",
                                    a,b,measured_geo_data[a][b]);
            }
            #endif

            {
                char *out_filename = new char[out_filename_prefix.size() + 30];
                sprintf(out_filename, "%s_%s_%d.out",
                        out_filename_prefix.c_str(), "geo", iter_num);
                std::ofstream out(out_filename);
                out << norm_geo_data;
                delete[] out_filename;
            }
            if (do_KL)
            {
                apply_geo_norm(fan_data, norm_geo_data);
                info(boost::format("KL %1%") % KL(measured_fan_data, fan_data, threshold_for_KL));
            }
            if (do_display)
            {
                fan_data.fill(1);
                apply_geo_norm(fan_data, norm_geo_data);
                display(fan_data, "geo norm");
            }

            
            // bucket norm
           {
                fan_data = model_fan_data;
                apply_efficiencies(fan_data, efficiencies);
                apply_geo_norm(fan_data, norm_geo_data);
                if (do_bucket)
                  iterate_bucket_norm(norm_bucket_data, measured_bucket_data, fan_data);
                 #if 0
                 { // check
                 for (int a=0; a<measured_bucket_data.get_length(); ++a)
                 for (int b=0; b<measured_bucket_data[0].get_length(); ++b)
                 if (norm_bucket_data[a][b]==0 && measured_bucket_data[a][b]!=0)
                 warning("bucket norm 0 at a=%d b=%d measured value=%g\n",
                 a,b,measured_bucket_data[a][b]);
                 }
                 #endif
                {
                    char *out_filename = new char[out_filename_prefix.size() + 30];
                    sprintf(out_filename, "%s_%s_%d.out",
                            out_filename_prefix.c_str(), "block", iter_num);
                    std::ofstream out(out_filename);
                    out << norm_bucket_data;
                    delete[] out_filename;
                }
                if (do_KL)
                {
                  apply_bucket_norm(fan_data, norm_bucket_data);
                    info(boost::format("KL %1%") % KL(measured_fan_data, fan_data, threshold_for_KL));
                }
                if (do_display)
                {
                    fan_data.fill(1);
                  apply_bucket_norm(fan_data, norm_bucket_data);
                    display(norm_bucket_data, "raw bucket norm");
                    display(fan_data, "bucket norm");
                }
            } // end bucket
  

 //// print KL for fansums
         if (do_KL)
       {
    Array<2,float> fan_sums(IndexRange2D(num_rings, num_detectors_per_ring));
    GeoData3D geo_data(num_axial_crystals_per_bucket, num_transaxial_crystals_per_bucket/2, num_rings, num_detectors_per_ring ); //inputes have to be modified
    BucketData3D bucket_data(num_axial_buckets, num_transaxial_buckets, num_axial_buckets - 1, num_transaxial_buckets - 1);
   
            make_fan_sum_data(fan_sums, fan_data);
            make_geo_data(geo_data, fan_data);
         make_bucket_data(bucket_data, measured_fan_data);
            
std::cerr << "KL on fans: " << KL(measured_fan_data, fan_data,0) << ", " << KL(measured_geo_data,geo_data,0) << std::endl;
}
        }
    }
    timer.stop();
    info(boost::format("CPU time %1% secs") % timer.value());
    return EXIT_SUCCESS;
}
