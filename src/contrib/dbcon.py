# Copyright (C) 2013 Associated Universities, Inc. Washington DC, USA.
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
# 
# Correspondence concerning GBT software should be addressed as follows:
#       GBT Operations
#       National Radio Astronomy Observatory
#       P. O. Box 2
#       Green Bank, WV 24944-0002 USA

from AIPS import AIPS
from AIPSTask import AIPSTask

import sys
import optparse

from aips_utils import Catalog

DISK_ID = 2                        # choose a good default work disk
BADDISK = 1                       # list a disk to avoid (0==no avoidance)
cat = Catalog()   # initialize a catalog object

def read_command_line(argv):
    """Read options from the command line."""
    # if no options are set, print help
    if len(argv) == 1:
        argv.append('-h')

    parser = optparse.OptionParser(description = 'Run the AIPS dbcon task to load '
                                   'calibrated spectra for imaging.')
    parser.add_option('--empty-catalog', dest = 'empty_catalog', action = 'store_true',
                      default = False, help = 'If set, will empty the AIPS catalog '
                      'without prompt before processing.  Otherwise, the user is '
                      'prompted to override the default False setting.')
    (options, args) = parser.parse_args()

    AIPS.userno = int(args[0])
    myfiles = args[1:]
    if not myfiles:
        print 'ERROR: No sdf files supplied.  Exiting.'
        sys.exit()

    cat.config(AIPS.userno, DISK_ID)  # configure the catalog object

    # start with a clean slate by trying to empty the catalog
    cat.empty(options.empty_catalog)
    
    return myfiles

def load_into_aips(myfiles):
    """Load files into AIPS with UVLOD task."""
    uvlod = AIPSTask('uvlod')
    uvlod.outdisk = DISK_ID            # write all input data to a select disk
    uvlod.userno = AIPS.userno

    first_file = True   # to help determine center freq to use

    for this_file in myfiles:        # input all AIPS single dish FITS files
        print 'Adding {0} to AIPS.'.format(this_file)
        uvlod.datain = 'PWD:' + this_file
        uvlod.go()
    
        # get the center frequency of the sdf file that was just loaded
        last = cat.last_entry()
        spectra = cat.get_uv(last)
        center_freq = spectra.header.crval[2]
    
        # if this is the first file loaded, look for
        # the same frequency in the next ones
        if first_file:
            expected_freq = center_freq
            first_file = False
        
        # if frequency of sdf file just loaded and 1st file differ by
        # more than 100 kHz, do not use the current file
        if abs(expected_freq - center_freq) > 1e5:
            print 'Frequencies differ: {0} != {1}'.format(center_freq, expected_freq)
            print '  Rejecting {0}'.format(this_file)
            spectra.zap()

def run_dbcon(entryA, entryB):
    """Combine the data in AIPS with the DBCON task"""
    dbcon = AIPSTask('dbcon')

    # always do firs
    dbcon.indisk = dbcon.outdisk = dbcon.in2disk = DISK_ID
    dbcon.userno = AIPS.userno
    
    file1 = cat.get_entry(entryA)
    dbcon.inname = file1.name
    dbcon.inclass = file1.klass
    dbcon.inseq = file1.seq
    
    file2 = cat.get_entry(entryB)
    dbcon.in2name = file2.name
    dbcon.in2class = file2.klass
    dbcon.in2seq = file2.seq
    
    dbcon.reweight[1] = 0
    dbcon.reweight[2] = 0
    
    print 'combining 1: ', dbcon.inname, dbcon.inclass, dbcon.inseq
    print 'combining 2: ', dbcon.in2name, dbcon.in2class, dbcon.in2seq
    
    dbcon.go()

def print_source_names():
    n_files = len(cat)
    
    source_names = set([])
    for x in range(n_files):
        entry = cat.get_entry(x)
        uvdata = cat.get_uv(entry)
        source_names.add(uvdata.header.object)

    print len(source_names), 'object(s) observed:', ', '.join(source_names)

def combine_files():
    """A containing function that chooses when to run the AIPS DBCON task."""

    n_files = len(cat)
    print_source_names()

    # if more than 1 file combine them with DBCON
    if n_files > 1:

        run_dbcon(0, 1)

        # and keep adding in one if there are more
        for ii in range(n_files-1, 1, -1):
            run_dbcon(-1, ii)
            cat.zap_entry(-2)   # zap previous dbcon to save space 

        # remove uv files
        for ii in range(n_files):
            cat.zap_entry(0)

def time_sort_data():
    """Time-sort data in AIPS with the UVSRT task."""
    uvsrt = AIPSTask('uvsrt')
    uvsrt.userno = AIPS.userno

    # -------------------------------------------------------------------------
    #    UVSRT the data
    # -------------------------------------------------------------------------

    # sort data to prevent down stream problems
    uvsrt.indisk = uvsrt.outdisk = DISK_ID
    uvsrt.baddisk[1] = BADDISK
    uvsrt.outcl = 'UVSRT'
    uvsrt.sort = 'TB'
    last = cat.last_entry()
    uvsrt.inname = last.name
    uvsrt.inclass = last.klass
    uvsrt.inseq = last.seq

    # will write to entry 1 because input sdf/uv files were removed
    uvsrt.go()

    cat.zap_entry(-1)  # remove the DBCON entry

def print_summary():
    """Print a simple summary to the screen of image RA/DEC and size."""
    # Extract the observations summary
    last = cat.last_entry()
    spectra = cat.get_uv(last)

    # and read parameters passed inside the spectra data header
    raDeg    = spectra.header.crval[3]
    decDeg   = spectra.header.crval[4]
    imxSize  = 2*round(spectra.header.crpix[3]/1.5 )
    imySize  = 2*round(spectra.header.crpix[4]/1.5 )
    cellsize = round(spectra.header.cdelt[4] * 3600.)
    print "Ra, Dec: {0:.2f} {1:.2f}  Image: x {2} y {3} cell {4}".format(raDeg, decDeg, imxSize, imySize, cellsize)


if __name__ == '__main__':
    
    sdf_filenames = read_command_line(sys.argv)
    load_into_aips(sdf_filenames)
    combine_files()
    print_summary()
    time_sort_data()
