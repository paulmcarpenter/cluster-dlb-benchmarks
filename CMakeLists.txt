# Copyright (C) 2021  Jimmy Aguilar Mena

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

cmake_minimum_required (VERSION 3.0)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/cmake")
find_package(MERCURIUM REQUIRED)

project (ClusterDLB)

option(WITH_ASAN "Build tests with address sanitizer" false)

set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)

# # Auxiliar function to declare mpi tests
# function (add_mpi_tests exec)
#   foreach (node ${ARGN})
#     set(testname ${exec}_${node})
#     add_test(NAME ${testname} COMMAND mpirun -np ${node} taskset -c 0-7 ./${exec})
#     message("Add test:  ${testname}")
#   endforeach ()
# endfunction ()

# # Add tests based on file list
# function (add_mpi_tests_list test_sources)
#   # Tests for varying numbers of nodes
#   foreach (test ${${test_sources}})
#     string(REGEX REPLACE "${PROJECT_SOURCE_DIR}/(.*)" "\\1" subfile ${test})
#     string(REPLACE "/" "_" testname ${subfile})
#     get_filename_component(exefile ${testname} NAME_WE)  # delete path and extension
#     # get_filename_component(cfile ${subfile} NAME)      # delete path
# 
#     message("Add executable: ${testname} ${subfile} ${exefile}")
# 
#     add_executable(${exefile} ${subfile} util.c)
#     target_link_libraries(${exefile} PRIVATE Threads::Threads)
#     add_mpi_tests(${exefile} ${ARGN})
#   endforeach ()
# endfunction ()

#Compilation flags
set(default_build_type "Debug")

# OmpSs-2
add_compile_options(-O0 -ggdb -g --ompss-2 -k -lm)
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} --ompss-2")

# MPI
add_compile_options(-I/apps/MVAPICH2/2.3rc1/INTEL/include -L/apps/MVAPICH2/2.3rc1/INTEL/lib -Wl,-rpath -Wl,/apps/MVAPICH2/2.3rc1/INTEL/lib -Wl,--enable-new-dtags -lmpi)
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -I/apps/MVAPICH2/2.3rc1/INTEL/include -L/apps/MVAPICH2/2.3rc1/INTEL/lib -Wl,-rpath -Wl,/apps/MVAPICH2/2.3rc1/INTEL/lib -Wl,--enable-new-dtags -lmpi")

# Enable address sanitizer
if (WITH_ASAN)
  message("Using ASAN")
  add_compile_options(-fno-omit-frame-pointer -fsanitize=address)

  set (CMAKE_EXE_LINKER_FLAGS
    "${CMAKE_EXE_LINKER_FLAGS} -fno-omit-frame-pointer -fsanitize=address")
endif ()


add_executable(check-redistribute tests/check-redistribute.c)
add_executable(dmalloc-redistribute tests/dmalloc-redistribute.c)
add_executable(lend tests/lend.c)
add_executable(synthetic_unbalanced synthetic/unbalanced.c)
add_executable(syntheticscatter syntheticscatter/syntheticscatter.c)
add_executable(syntheticslow syntheticslow/syntheticslow.c)

add_test(NAME check_num_nodes COMMAND check_num_nodes.py --expect 2)
add_test(NAME check-redistribute-degree-1 COMMAND runhybrid.py --debug false --vranks 4 --local --degree 1 --local-period 120 --monitor 200  ./check-redistribute)
add_test(NAME check-redistribute-degree-2 COMMAND runhybrid.py --debug false --vranks 4 --local --degree 2 --local-period 120 --monitor 200  ./check-redistribute)
add_test(NAME dmalloc-redistribute-degree-1 COMMAND runhybrid.py --debug false --vranks 4 --local --degree 1 --local-period 120 --monitor 200  ./dmalloc-redistribute)
add_test(NAME dmalloc-redistribute-degree-2 COMMAND runhybrid.py --debug false --vranks 4 --local --degree 2 --local-period 120 --monitor 200  ./dmalloc-redistribute)
add_test(NAME lend-degree-2 COMMAND runhybrid.py --debug false --vranks 2 --local --degree 2 --local-period 120 --monitor 200 ./lend)

include_directories(${PROJECT_SOURCE_DIR})

#Add the unit tests
enable_testing()

# # Tests specifically on many ranks
# file(GLOB test_sources_all manual/*.c)
# add_mpi_tests_list(test_sources_all 1 2 3 15 16)
# 
# # If we add more numeric specific tests we can use a loop for this.
# # But for now this is enough.
# 
# file(GLOB test_sources_2 nasty/test2_*.c)
# add_mpi_tests_list(test_sources_2 2)
# 
# file(GLOB test_sources_3 nasty/test3_*.c)
# add_mpi_tests_list(test_sources_3 3)
# 
# file(GLOB test_sources_4 nasty/test4_*.c)
# add_mpi_tests_list(test_sources_4 4)
# 
# set(USE_NAMESPACE_TOML false)
# if (WITH_NAMESPACE)
#   message("-- Using NAMESPACE")
#   set(USE_NAMESPACE_TOML true)
# 
#   file(GLOB test_namespace namespace/*[!_][!*].c)
#   add_mpi_tests_list(test_namespace 3)
# 
#   file(GLOB test_namespace namespace/*_4.c)
#   add_mpi_tests_list(test_namespace 4)
# endif ()

#add the install targets
file(MAKE_DIRECTORY "${CMAKE_BINARY_DIR}/log")
