#!/usr/bin/env python3
'''Extract And Align Coding Regions Across Multiple Plastomes'''
__version__ = 'm.gruenstaeudl@fu-berlin.de|2022-09-09T16:22:47 CEST'

#-----------------------------------------------------------------#
## IMPORTS
import argparse
import Bio
from Bio import SeqIO  # line is necessary for similar reason stated in: https://www.biostars.org/p/13099/
from Bio.Align import Applications  # line is necessary for similar reason stated in: https://www.biostars.org/p/13099/
import collections
import io  # For file handles
import os
import subprocess
import sys

#from Bio.SeqRecord import SeqRecord
#from Bio import AlignIO  # For function 'AlignIO.convert'
#from Bio.Nexus import Nexus  # For functions 'Nexus.combine' and 'Nexus.Nexus'
#from Bio.Align.Applications import MafftCommandline
#from Bio.Seq import Seq

#-----------------------------------------------------------------#
# DEBUGGING HELP
import pdb
#pdb.set_trace()

#-----------------------------------------------------------------#
# VARIABLES
path_to_this_script = os.path.dirname(os.path.realpath(__file__))
path_to_back_transl_helper = path_to_this_script + '/align_back_trans.py'
if not os.path.isfile(path_to_back_transl_helper):
    raise Exception("  ERROR: Cannot find `align_back_trans.py` not alongside this script")

#-----------------------------------------------------------------#
# FUNCTIONS
def extract_collect_CDS(masterdict_nucl, masterdict_prot, inFn, fmt='genbank'):
    rec = Bio.SeqIO.read(inFn, fmt)
    for feature in rec.features:
        if feature.type == 'CDS':
            if 'gene' in feature.qualifiers:
                gene_name = feature.qualifiers['gene'][0]
                seq_name = gene_name + '_' + rec.name

                # Nucleotide sequences
                seq_obj = feature.extract(rec).seq
                seq_rec = Bio.SeqRecord.SeqRecord(seq_obj, id=seq_name, name='', description='')
                if gene_name in masterdict_nucl.keys():
                    tmp = masterdict_nucl[gene_name]
                    tmp.append(seq_rec)
                    masterdict_nucl[gene_name] = tmp
                else:
                    masterdict_nucl[gene_name] = [seq_rec]

                # Protein sequences
                    # DON'T USE QUALIFIER 'TRANSLATION', AS GENES WITH INTRONS ARE COUNTED TWICE;
                    # KEEP TRANSLATING FROM EXTRACT
                    #if 'translation' in feature.qualifiers:
                    #    transl = feature.qualifiers['translation'][0]
                    #    seq_obj = Bio.Seq.Seq(transl, IUPAC.protein)
                    #else:
                    #    seq_obj = feature.extract(rec).seq.translate(table=11, cds=True)
                seq_obj = feature.extract(rec).seq.translate(table=11)#, cds=True)
                seq_rec = Bio.SeqRecord.SeqRecord(seq_obj, id=seq_name, name='', description='')
                if gene_name in masterdict_prot.keys():
                    tmp = masterdict_prot[gene_name]
                    tmp.append(seq_rec)
                    masterdict_prot[gene_name] = tmp
                else:
                    masterdict_prot[gene_name] = [seq_rec]

def remove_duplicates(my_dict):
    for k,v in my_dict.items():
        idtags = []
        for counter, seqrec in enumerate(v):
            if seqrec.id in idtags:
                #v.pop(counter)
                del v[counter]
            else:
                idtags.append(seqrec.id)
        my_dict[k] = v
    #return my_dict

def main(args):
    
    # UNPACKING INPUT PARAMETERS
    inDir = args.inpd
    if not os.path.exists(inDir):
        raise Exception("  ERROR: Input directory `%s` does not exist." % inDir)
    outDir = args.outd
    if not os.path.exists(outDir):
        raise Exception("  ERROR: Output directory `%s` does not exist." % outDir)
    fileext = args.fileext
    exclude_list = args.excllist

    # SET UP EMPTY ORDERED DICTIONARIES
    masterdict_nucl = collections.OrderedDict()
    masterdict_prot = collections.OrderedDict()
    
    # EXTRACT AND COLLECT CDS FROM RECORDS
    files = [f for f in os.listdir(inDir) if f.endswith(fileext)]
    for f in files:
        extract_collect_CDS(masterdict_nucl, masterdict_prot, os.path.join(inDir, f))

    # REMOVE ALL DUPLICATE ENTRIES (result of CDS with multiple exons)
    remove_duplicates(masterdict_nucl)
    remove_duplicates(masterdict_prot)
    # Note: Not sure why I have to run this removal twice, but not all 
    #       duplicates are removed first time around.
    remove_duplicates(masterdict_nucl)
    remove_duplicates(masterdict_prot)

    # REMOVE ORFs (OPTIONAL!)
    list_of_orfs = [orf for orf in masterdict_nucl.keys() if "orf" in orf]
    for orf in list_of_orfs:
        del masterdict_nucl[orf]
        del masterdict_prot[orf]

    # REMOVE SPECIFIC GENES (OPTIONAL!)
    if exclude_list:
        for excluded in exclude_list:
            if excluded in masterdict_nucl:
                del masterdict_nucl[excluded]
                del masterdict_prot[excluded]
            else:
                raise Exception("  ERROR: Gene to be excluded not found in infile.")

    # ALIGN AND WRITE TO FILE
    if masterdict_nucl.items():
        for k,v in masterdict_nucl.items():
            outFn_unalign_nucl = os.path.join(outDir, 'nucl_'+k+'.unalign.fasta')
            # Write unaligned nucleotide sequences
            with open(outFn_unalign_nucl, 'w') as hndl:
                Bio.SeqIO.write(v, hndl, 'fasta')
    if not masterdict_nucl.items():
        raise Exception("  ERROR: No items in nucleotide masterdictionary.")

    if masterdict_prot.items():
        for k,v in masterdict_prot.items():
            outFn_unalign_prot = os.path.join(outDir, 'prot_'+k+'.unalign.fasta')
            outFn_aligned_prot = os.path.join(outDir, 'prot_'+k+'.aligned.fasta')
            # WRITE UNALIGNED PROTEIN SEQUENCES
            with open(outFn_unalign_prot, 'w') as hndl:
                Bio.SeqIO.write(v, hndl, 'fasta')
            # ALIGN SEQUENCES
            #import subprocess
            #subprocess.call(['mafft', '--auto', outFn_unalign_prot, '>', outFn_aligned_prot])
            mafft_cline = Bio.Align.Applications.MafftCommandline(input=outFn_unalign_prot)
            stdout, stderr = mafft_cline()
            with open(outFn_aligned_prot, 'w') as hndl:
                hndl.write(stdout)
    if not masterdict_prot.items():
        raise Exception("  ERROR: No items in protein masterdictionary.")

    # BACK-TRANSLATION via Python script by Peter Cook
    # https://github.com/peterjc/pico_galaxy/tree/master/tools/align_back_trans
    for k,v in masterdict_prot.items():
        outFn_unalign_nucl = os.path.join(outDir, 'nucl_'+k+'.unalign.fasta')
        outFn_aligned_nucl = os.path.join(outDir, 'nucl_'+k+'.aligned.fasta')
        outFn_aligned_prot = os.path.join(outDir, 'prot_'+k+'.aligned.fasta')
        try:
            cmd = ['python3', path_to_back_transl_helper, 'fasta', outFn_aligned_prot, outFn_unalign_nucl, outFn_aligned_nucl, '11']
            log = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        except:
            raise Exception("  ERROR: Cannot conduct back-translation of `%s`. Command used: %s" % (k, ' '.join(cmd)))

    # CONVERT FASTA ALIGNMENT TO NEXUS ALIGNMENT AND APPEND FOR CONCATENATION
    alignm_L = []
    for k in masterdict_prot.keys():
        aligned_nucl_fasta = os.path.join(outDir, 'nucl_'+k+'.aligned.fasta')
        aligned_nucl_nexus = os.path.join(outDir, 'nucl_'+k+'.aligned.nexus')

        # CONVERT FASTA ALIGNMENT TO NEXUS ALIGNMENT
        try:
            Bio.AlignIO.convert(aligned_nucl_fasta, 'fasta', aligned_nucl_nexus, 'nexus', molecule_type='DNA')
        except:
            raise Exception("  ERROR: Cannot convert alignment of `%s` from FASTA to NEXUS" % k)
            
        # IMPORT NEXUS AND APPEND TO LIST FOR CONCATENATION
        try:
            alignm_nexus = Bio.AlignIO.read(aligned_nucl_nexus, 'nexus')
            hndl = io.StringIO()
            Bio.AlignIO.write(alignm_nexus, hndl, 'nexus')
            nexus_string = hndl.getvalue()
            nexus_string = nexus_string.replace('\n'+k+'_', '\ncombined_')  # IMPORTANT: Stripping the gene name from the sequence name
            alignm_nexus = Bio.Nexus.Nexus.Nexus(nexus_string)
            alignm_L.append((k, alignm_nexus)) # Function 'Bio.Nexus.Nexus.combine' needs a tuple.
        except:
            raise Exception("  ERROR: Cannot add alignment of `%s` to concatenation" % k)

    # COMBINE NEXUS ALIGNMENTS (IN NO PARTICULAR ORDER)
    alignm_combined = Bio.Nexus.Nexus.combine(alignm_L) # Function 'Bio.Nexus.Nexus.combine' needs a tuple.
    outFn_nucl_combined_fasta = os.path.join(outDir, 'nucl_'+str(len(alignm_L))+'combined.aligned.fasta')
    outFn_nucl_combined_nexus = os.path.join(outDir, 'nucl_'+str(len(alignm_L))+'combined.aligned.nexus')
    alignm_combined.write_nexus_data(filename=open(outFn_nucl_combined_nexus, 'w'))
    Bio.AlignIO.convert(outFn_nucl_combined_nexus, 'nexus', outFn_nucl_combined_fasta, 'fasta')

#-----------------------------------------------------------------#
# MAIN
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Author|Version: '+__version__)
    # Required
    parser.add_argument("--inpd", "-i", type=str, required=True, 
                        help="path to input directory (which contains the GenBank files)",
                        default="./input")
    # Optional
    parser.add_argument("--outd", "-o", type=str, required=False, 
                        help="(Optional) Path to output directory",
                        default="./output")
    parser.add_argument("--fileext", "-f", type=str, required=False, 
                        help="(Optional) File extension of input files", 
                        default=".gb")
    parser.add_argument("--excllist", "-e", type=list, required=False, 
                        default=['rps12', 'ycf3'], 
                        help="(Optional) List of genes to be excluded")
    parser.add_argument("--verbose", "-v", action="version", version="%(prog)s "+__version__, 
                        help="(Optional) Enable verbose logging", default=True)
    args = parser.parse_args()
    main(args)

#-----------------------------------------------------------------#
#EOF
#-----------------------------------------------------------------#
