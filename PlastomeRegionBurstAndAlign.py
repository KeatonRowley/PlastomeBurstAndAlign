#!/usr/bin/env python3
""" Extracts and aligns coding and non-coding regions across multiple plastid genomes
"""
__version__ = "m_gruenstaeudl@fhsu.edu|Thu 09 Nov 2023 10:18:47 PM CST"

# ------------------------------------------------------------------------------#
# IMPORTS
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from Bio import (
    SeqIO, Nexus, SeqRecord, AlignIO
)  # line necessary; see: https://www.biostars.org/p/13099/
from Bio.Align import (
    Applications
)  # line necessary; see: https://www.biostars.org/p/13099/
from Bio.SeqFeature import (
    FeatureLocation, CompoundLocation, ExactPosition
)
import coloredlogs
from collections import OrderedDict
from copy import deepcopy
from io import StringIO
import logging
import os
from re import sub
import subprocess
# ------------------------------------------------------------------------------#
# DEBUGGING HELP
# import ipdb
# ipdb.set_trace()
# -----------------------------------------------------------------#
# CLASSES AND FUNCTIONS


class ExtractAndCollect:

    def __init__(self, main_odict_nucl):
        self.main_odict_nucl = main_odict_nucl

    def extract_cds(self, main_odict_prot, rec, min_seq_length):
        """ Extracts all CDS (coding sequences = genes) from a given sequence record
        OUTPUT: saves to global main_odict_nucl and to global main_odict_prot
        """
        for feature in rec.features:
            if feature.type == "CDS":
                if "gene" in feature.qualifiers:
                    gene_name = feature.qualifiers["gene"][0]
                    seq_name = gene_name + "_" + rec.name

                    # Step 1. Extract nucleotide sequence of each gene
                    seq_obj = feature.extract(rec).seq
                    seq_rec = SeqRecord.SeqRecord(
                        seq_obj, id=seq_name, name="", description=""
                    )
                    if gene_name in self.main_odict_nucl.keys():
                        tmp = self.main_odict_nucl[gene_name]
                        tmp.append(seq_rec)
                        self.main_odict_nucl[gene_name] = tmp
                    else:
                        self.main_odict_nucl[gene_name] = [seq_rec]

                    # Step 2. Translate nucleotide sequence to amino acid sequence
                    seq_obj = feature.extract(rec).seq.translate(
                        table=11
                    )  # , cds=True)

                    # Step 3. Test for minimum sequence length
                    if len(seq_obj) >= min_seq_length:
                        pass
                    else:
                        continue

                    # Step 4. Save protein sequence to output dictionary
                    seq_rec = SeqRecord.SeqRecord(
                        seq_obj, id=seq_name, name="", description=""
                    )
                    if gene_name in main_odict_prot.keys():
                        tmp = main_odict_prot[gene_name]
                        tmp.append(seq_rec)
                        main_odict_prot[gene_name] = tmp
                    else:
                        main_odict_prot[gene_name] = [seq_rec]

    def extract_igs(self, rec, fname, min_seq_length):
        """ Extracts all IGS (intergenic spacers) from a given sequence record
        OUTPUT: saves to global main_odict_nucl
        """
        # Step 1. Extract all genes from record (i.e., cds, trna, rrna)
        # Resulting list contains adjacent features in order of appearance on genome
        # Note: No need to include "if feature.type=='tRNA'", because all tRNAs are also annotated as genes
        all_genes = [
            f for f in rec.features
            if (f.type == "gene" and "gene" in f.qualifiers)
        ]
        # Note: The statement "if feature.qualifier['gene'][0] not 'matK'" is necessary, as matK is located inside trnK
        # TO DO #
        # Isn't there a better way to handle matK?!
        all_genes_minus_matk = [
            f for f in all_genes if f.qualifiers["gene"][0] != "matK"
        ]

        # Step 2. Loop through genes
        for count, idx in enumerate(range(0, len(all_genes_minus_matk) - 1), 1):
            cur_feat = all_genes_minus_matk[idx]
            cur_feat_name = cur_feat.qualifiers["gene"][0]
            adj_feat = all_genes_minus_matk[idx + 1]
            adj_feat_name = adj_feat.qualifiers["gene"][0]

            # Step 3. Define names of IGS
            if "gene" in cur_feat.qualifiers and "gene" in adj_feat.qualifiers:
                cur_feat_name_safe = cur_feat_name.replace("-", "_")
                cur_feat_name_safe = sub(r"\W", "", cur_feat_name_safe)
                adj_feat_name_safe = adj_feat_name.replace("-", "_")
                adj_feat_name_safe = sub(r"\W", "", adj_feat_name_safe)
                igs_name = cur_feat_name_safe + "_" + adj_feat_name_safe
                inv_igs_name = adj_feat_name_safe + "_" + cur_feat_name_safe

                # Only operate on genes that do not have compound locations (as it only messes things up)
                if (
                    type(cur_feat.location) is not CompoundLocation
                    and type(adj_feat.location) is not CompoundLocation
                ):
                    # Step 4. Make IGS SeqFeature
                    start_pos = ExactPosition(
                        cur_feat.location.end
                    )  # +1)  Note: It's unclear if +1 is needed here.
                    end_pos = ExactPosition(adj_feat.location.start)
                    if int(start_pos) >= int(end_pos):
                        continue  # If there is no IGS, then simply skip this gene pair
                    else:
                        try:
                            exact_location = FeatureLocation(start_pos, end_pos)
                        except Exception as e:
                            log.warning(
                                f"\t{fname}: Exception occurred for IGS between "
                                f"`{cur_feat_name}` (start pos: {start_pos}) and "
                                f"`{adj_feat_name}` (end pos:{end_pos}). "
                                f"Skipping this IGS ...\n"
                                f"Error message: {e}"
                            )
                            continue
                    # Step 5. Make IGS SeqRecord
                    seq_obj = exact_location.extract(rec).seq
                    seq_name = igs_name + "_" + rec.name
                    seq_rec = SeqRecord.SeqRecord(
                        seq_obj, id=seq_name, name="", description=""
                    )
                    # Step 6. Testing for minimum sequence length
                    if len(seq_obj) >= min_seq_length:
                        pass
                    else:
                        continue
                    # Step 7. Attach seqrecord to growing dictionary
                    if (
                        igs_name in self.main_odict_nucl.keys()
                        or inv_igs_name in self.main_odict_nucl.keys()
                    ):
                        if igs_name in self.main_odict_nucl.keys():
                            tmp = self.main_odict_nucl[igs_name]
                            tmp.append(seq_rec)
                            self.main_odict_nucl[igs_name] = tmp
                        if inv_igs_name in self.main_odict_nucl.keys():
                            pass  # Don't count IGS in the IRs twice
                    else:
                        self.main_odict_nucl[igs_name] = [seq_rec]
                # Handle genes with compound locations
                else:
                    log.warning(
                        f"{fname}: the IGS between `{cur_feat_name}` and `{adj_feat_name}` is "
                        f"currently not handled and would have to be extracted manually. "
                        f"Skipping this IGS ...")
                    continue

    def extract_int(self, main_odict_intron2, rec):
        """ Extracts all INT (introns) from a given sequence record
        OUTPUT: saves to global main_odict_nucl
        """
        for feature in rec.features:
            if feature.type == "CDS" or feature.type == "tRNA":
                try:
                    gene_name_base = feature.qualifiers["gene"][0]
                    gene_name_base_safe = gene_name_base.replace("-", "_")
                    gene_name_base_safe = sub(r"\W", "", gene_name_base_safe)
                except Exception as e:
                    log.warning(
                        f"Unable to extract gene name for CDS starting "
                        f"at `{feature.location.start}` of `{rec.id}`. "
                        f"Skipping feature ...\n"
                        f"Error message: {e}"
                    )
                    continue
                # Step 1. Limiting the search to CDS containing introns
                # Step 1.a. If one intron in gene:
                if len(feature.location.parts) == 2:
                    try:
                        gene_name = gene_name_base_safe + "_intron1"
                        seq_rec, gene_name = extract_intron_internal(
                            rec, feature, gene_name, 0
                        )
                        if gene_name not in self.main_odict_nucl.keys():
                            self.main_odict_nucl[gene_name] = [seq_rec]
                        else:
                            self.main_odict_nucl[gene_name].append(seq_rec)
                    except Exception as e:
                        some_id = list(feature.qualifiers.values())[0]
                        log.warning(
                            f"An error for `{some_id}` occurred.\n"
                            f"Error message: {e}"
                        )
                        pass
                # Step 1.b. If two introns in gene:
                if len(feature.location.parts) == 3:
                    copy_feature = deepcopy(
                        feature
                    )  # Important b/c feature is overwritten in extract_intron_internal()
                    try:
                        gene_name = gene_name_base_safe + "_intron1"
                        seq_rec, gene_name = extract_intron_internal(
                            rec, feature, gene_name, 0
                        )
                        if gene_name not in self.main_odict_nucl.keys():
                            self.main_odict_nucl[gene_name] = [seq_rec]
                        else:
                            self.main_odict_nucl[gene_name].append(seq_rec)
                    except Exception as e:
                        some_id = list(feature.qualifiers.values())[0]
                        log.critical(
                            f"An error for `{some_id}` occurred.\n"
                            f"Error message: {e}"
                        )
                        raise Exception()
                        # pass
                    feature = copy_feature
                    try:
                        gene_name = gene_name_base_safe + "_intron2"
                        seq_rec, gene_name = extract_intron_internal(
                            rec, feature, gene_name, 1
                        )
                        if gene_name not in main_odict_intron2.keys():
                            main_odict_intron2[gene_name] = [seq_rec]
                        else:
                            main_odict_intron2[gene_name].append(seq_rec)
                    except Exception as e:
                        some_id = list(feature.qualifiers.values())[0]
                        log.warning(
                            f"An issue occurred for gene `{some_id}`.\n"
                            f"Error message: {e}"
                        )
                        pass


# -----------------------------------------------------------------#
def mafft_align(input_file, output_file, num_threads):
    # LEGACY WAY:
    # import subprocess
    # subprocess.call(['mafft', '--auto', out_fn_unalign_prot, '>', out_fn_aligned_prot])
    # CURRENT WAY:
    # Perform sequence alignment using MAFFT
    mafft_cline = Applications.MafftCommandline(
        input=input_file, adjustdirection=True, thread=num_threads
    )
    stdout, stderr = mafft_cline()
    with open(output_file, "w") as hndl:
        hndl.write(stdout)


# ------------------------------------------------------------------------------#
# TO DO #
# The function "extract_intron_internal()" is currently not being used and needs to be integrated
def extract_intron_internal(rec, feature, gene_name, offset):
    try:
        feature.location = FeatureLocation(
            feature.location.parts[offset].end, feature.location.parts[offset + 1].start
        )
    except Exception:
        feature.location = FeatureLocation(
            feature.location.parts[offset + 1].start, feature.location.parts[offset].end
        )
    try:
        seq_name = gene_name + "_" + rec.name
        seq_obj = feature.extract(rec).seq  # Here the actual extraction is conducted
        seq_rec = SeqRecord.SeqRecord(
            seq_obj, id=seq_name, name="", description=""
        )
        return seq_rec, gene_name
    except Exception as e:
        log.critical(
            f"Unable to conduct intron extraction for {feature.qualifiers['gene']}.\n"
            f"Error message: {e}"
        )
        raise Exception()


# ------------------------------------------------------------------------------#
def remove_duplicates(my_dict):
    for k, v in my_dict.items():
        unique_items = []
        seen_ids = set()
        for seqrec in v:
            if seqrec.id not in seen_ids:
                seen_ids.add(seqrec.id)
                unique_items.append(seqrec)
        my_dict[k] = unique_items
    # No need to return my_dict because it is modified in place


# ------------------------------------------------------------------------------#
# MAIN HELPER FUNCTIONS
# ------------------------------------------------------------------------------#
def setup_logger(verbose):
    global log
    log = logging.getLogger(__name__)
    log_format = "%(asctime)s [%(levelname)s] %(message)s"
    log_level = logging.DEBUG if verbose else logging.INFO
    coloredlogs.install(fmt=log_format, level=log_level, logger=log)


def unpack_input_parameters(args):
    in_dir = args.inpd
    if not os.path.exists(in_dir):
        logging.critical(f"Input directory `{in_dir}` does not exist.")
        raise Exception()
    global out_dir
    out_dir = args.outd
    if not os.path.exists(out_dir):
        logging.critical(f"Output directory `{out_dir}` does not exist.")
        raise Exception()

    fileext = args.fileext
    exclude_list = args.excllist
    min_seq_length = args.minseqlength
    min_num_taxa = args.minnumtaxa
    select_mode = args.selectmode.lower()
    verbose = args.verbose
    return (
        in_dir,
        out_dir,
        fileext,
        exclude_list,
        min_seq_length,
        min_num_taxa,
        select_mode,
        verbose,
    )


def parse_infiles_and_extract_annos(in_dir, fileext, select_mode, min_seq_length):
    """ Loads all genome records of a given folder one by one, parses each, and extracts
    all annotations in accordance with the user input
    INPUT:  file location, user specification on cds/int/igs to extract, min_seq_length
    OUTPUT: nucleotide and protein dictionaries
    """
    log.info("parse genome records and extract their annotations")
    main_odict_nucl = OrderedDict()
    main_odict_prot = OrderedDict() if select_mode == "cds" else None
    main_odict_intron2 = OrderedDict() if select_mode == "int" else None

    files = [f for f in os.listdir(in_dir) if f.endswith(fileext)]
    for f in files:
        log.info(f"parsing GenBank flatfile `{f}`")
        rec = SeqIO.read(os.path.join(in_dir, f), "genbank")
        # TO DO #
        # Warning 'BiopythonWarning: Partial codon, len(sequence) not a multiple of three.' occurs in line above:
        # Is there a way to suppress the warning in line above but activate a flag which would allow us to
        # solve it in individual function?
        if select_mode == "cds":
            ExtractAndCollect(main_odict_nucl).extract_cds(
                main_odict_prot, rec, min_seq_length
            )
        if select_mode == "igs":
            ExtractAndCollect(main_odict_nucl).extract_igs(rec, f, min_seq_length)
        if select_mode == "int":
            ExtractAndCollect(main_odict_nucl).extract_int(main_odict_intron2, rec)
            main_odict_nucl.update(main_odict_intron2)

        if not main_odict_nucl.items():
            log.critical(f"No items in main dictionary: {out_dir}")
            raise Exception()

    return main_odict_nucl, main_odict_prot


def remove_duplicate_annos(main_odict_nucl, main_odict_prot, select_mode):
    log.info("removing duplicate annotations")
    remove_duplicates(main_odict_nucl)
    if select_mode == "cds":
        remove_duplicates(main_odict_prot)


def remove_annos_if_below_minnumtaxa(main_odict_nucl, main_odict_prot, min_num_taxa):
    log.info(f"removing annotations that occur in fewer than `{min_num_taxa}` taxa")
    for k, v in main_odict_nucl.items():
        if len(v) < min_num_taxa:
            del main_odict_nucl[k]
            if main_odict_prot:
                del main_odict_prot[k]


def remove_orfs(main_odict_nucl, main_odict_prot):
    log.info("removing ORFs")
    list_of_orfs = [orf for orf in main_odict_nucl.keys() if "orf" in orf]
    for orf in list_of_orfs:
        del main_odict_nucl[orf]
        if main_odict_prot:
            del main_odict_prot[orf]


def remove_user_defined_genes(
    main_odict_nucl, main_odict_prot, exclude_list, select_mode
):
    log.info("removing user-defined genes")
    if exclude_list:
        if select_mode == "int":
            to_be_excluded = [i + "_intron1" for i in exclude_list] + [
                i + "_intron2" for i in exclude_list
            ]
            exclude_list = to_be_excluded
        for excluded in exclude_list:
            if excluded in main_odict_nucl:
                del main_odict_nucl[excluded]
                if select_mode == "cds" and main_odict_prot:
                    del main_odict_prot[excluded]
            else:
                log.warning(
                    f"Region `{excluded}` to be excluded but unable to be found in infile."
                )
                pass


def save_regions_as_unaligned_matrices(main_odict_nucl):
    """ Takes a dictionary of nucleotide sequences and saves all sequences of the same region
    into an unaligned nucleotide matrix
    INPUT: dictionary of sorted nucleotide sequences of all regions
    OUTPUT: unaligned nucleotide matrix for each region, saved to file
    """
    log.info("saving individual regions as unaligned nucleotide matrices")
    for k, v in main_odict_nucl.items():
        # Define input and output names
        out_fn_unalign_nucl = os.path.join(out_dir, "nucl_" + k + ".unalign.fasta")
        with open(out_fn_unalign_nucl, "w") as hndl:
            SeqIO.write(v, hndl, "fasta")


def multiple_sequence_alignment_nucleotide(main_odict_nucl):
    """
    Iterates over all unaligned nucleotide matrices and aligns each via a third-party software tool
    INPUT:  - dictionary of sorted nucleotide sequences of all regions (used only for region names!)
            - unaligned nucleotide matrices (present as files in FASTA format)
    OUTPUT: aligned nucleotide matrices (present as files in FASTA format)
    """
    log.info("conducting MSA based on nucleotide sequence data")
    if main_odict_nucl.items():
        for k in main_odict_nucl.keys():
            # Define input and output names
            out_fn_unalign_nucl = os.path.join(out_dir, "nucl_" + k + ".unalign.fasta")
            out_fn_aligned_nucl = os.path.join(out_dir, "nucl_" + k + ".aligned.fasta")

            # Step 1. Determine number of CPU core available
            # TO DO #
            # Automatically determine number of threads available #
            # Have the number of threads saved as num_threads
            num_threads = 1
            # Step 2. Align matrices based on their NUCLEOTIDE sequences via third-party alignment tool
            # TO DO #
            # Let user choose if alignment conducted with MAFFT, MUSCLE, CLUSTAL, etc.;
            # use a new argparse argument and if statements in line below
            mafft_align(out_fn_unalign_nucl, out_fn_aligned_nucl, num_threads)
    else:
        log.critical("No items in nucleotide main dictionary to process")
        raise Exception()


def process_protein_alignment(k, v, path_to_back_transl_helper, num_threads):
    # Define input and output names
    out_fn_unalign_prot = os.path.join(out_dir, f"prot_{k}.unalign.fasta")
    out_fn_aligned_prot = os.path.join(out_dir, f"prot_{k}.aligned.fasta")
    out_fn_unalign_nucl = os.path.join(out_dir, f"nucl_{k}.unalign.fasta")
    out_fn_aligned_nucl = os.path.join(out_dir, f"nucl_{k}.aligned.fasta")

    # Step 1. Write unaligned protein sequences to file
    with open(out_fn_unalign_prot, "w") as hndl:
        SeqIO.write(v, hndl, "fasta")

    # Step 2. Align matrices based on their PROTEIN sequences via third-party alignment tool
    mafft_align(out_fn_unalign_prot, out_fn_aligned_prot, num_threads)

    # Step 4. Conduct actual back-translation from PROTEINS TO NUCLEOTIDES
    # Note: For some reason, the path_to_back_transl_helper spits only works
    # if FASTA files are specified, not if NEXUS files are specified
    cmd = [
        "python3",
        path_to_back_transl_helper,
        "fasta",
        out_fn_aligned_prot,
        out_fn_unalign_nucl,
        out_fn_aligned_nucl,
        "11",
    ]
    try:
        subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        cmd_prt = " ".join(cmd)
        log.warning(
            f"Unable to conduct back-translation of `{k}`. "
            f"Command used: {cmd_prt}. "
            f"Error message: {e.output.decode('utf-8').strip()}."
        )


def conduct_protein_alignment_and_back_translation(main_odict_prot):
    """ Iterates over all unaligned PROTEIN matrices, aligns them as proteins via
    third-party software, and back-translates each alignment to NUCLEOTIDES
    INPUT:  dictionary of sorted PROTEIN sequences of all regions
    OUTPUT: aligned nucleotide matrices (present as files in NEXUS format)
    """
    log.info("conducting MSA based on protein sequence data, followed by back-translation to nucleotides")

    # Step X. Determine number of CPU core available
    num_threads = os.cpu_count()  # Automatically determine number of threads available

    # Step 3. Check if back-translation script exists
    path_to_back_transl_helper = os.path.join(
        os.path.dirname(__file__), "align_back_trans.py"
    )
    if not os.path.isfile(path_to_back_transl_helper):
        log.critical("Unable to find `align_back_trans.py` alongside this script")
        raise Exception("Back-translation helper script not found")

    # Use ThreadPoolExecutor to parallelize the alignment and back-translation tasks
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        future_to_protein = {
            executor.submit(
                process_protein_alignment,
                k,
                v,
                path_to_back_transl_helper,
                num_threads,
            ): k
            for k, v in main_odict_prot.items()
        }

        for future in as_completed(future_to_protein):
            k = future_to_protein[future]
            try:
                future.result()  # If needed, you can handle results here

            except Exception as e:
                log.error("%r generated an exception: %s" % (k, e))


def collect_successful_alignments(main_odict_nucl):
    """ Converts alignments to NEXUS format; then collect all successfully generated alignments
    INPUT:  dictionary of region names
    OUTPUT: list of alignments
    """
    log.info("collecting all successful alignments")
    success_list = []
    for k in main_odict_nucl.keys():
        # Step 1. Define input and output names
        aligned_nucl_fasta = os.path.join(out_dir, "nucl_" + k + ".aligned.fasta")
        aligned_nucl_nexus = os.path.join(out_dir, "nucl_" + k + ".aligned.nexus")
        # Step 2. Convert FASTA alignment to NEXUS alignment
        try:
            AlignIO.convert(
                aligned_nucl_fasta,
                "fasta",
                aligned_nucl_nexus,
                "nexus",
                molecule_type="DNA",
            )
        except Exception as e:
            log.warning(
                f"Unable to convert alignment of `{k}` from FASTA to NEXUS.\n"
                f"Error message: {e}"
            )
            continue  # skip to next k in loop, so that k is not included in success_list
        # Step 3. Import NEXUS files and append to list for concatenation
        try:
            alignm_nexus = AlignIO.read(aligned_nucl_nexus, "nexus")
            hndl = StringIO()
            AlignIO.write(alignm_nexus, hndl, "nexus")
            nexus_string = hndl.getvalue()
            # The following line replaces the gene name of sequence name with 'concat_'
            nexus_string = nexus_string.replace('\n'+k+'_', '\nconcat_')
            alignm_nexus = Nexus.Nexus.Nexus(nexus_string)
            success_list.append(
                (k, alignm_nexus)
            )  # Function 'Nexus.Nexus.combine' needs a tuple.
        except Exception as e:
            log.warning(
                f"Unable to add alignment of `{k}` to concatenation.\n"
                f"Error message: {e}"
            )
            pass
    return success_list


def concatenate_successful_alignments(success_list):
    log.info("concatenate all successful alignments (in no particular order)")
    # Step 1. Define output names
    out_fn_nucl_concat_fasta = os.path.join(
        out_dir, "nucl_" + str(len(success_list)) + "concat.aligned.fasta"
    )
    out_fn_nucl_concat_nexus = os.path.join(
        out_dir, "nucl_" + str(len(success_list)) + "concat.aligned.nexus"
    )
    # Step 2. Do concatenation
    try:
        alignm_concat = Nexus.Nexus.combine(
            success_list
        )  # Function 'Nexus.Nexus.combine' needs a tuple
    except Exception as e:
        log.critical(
            "Unable to concatenate alignments.\n"
            f"Error message: {e}"
        )
        raise Exception()
    # Step 3. Write concatenated alignments to file in NEXUS format
    alignm_concat.write_nexus_data(filename=open(out_fn_nucl_concat_nexus, "w"))
    # Step 4. Convert the NEXUS file just generated to FASTA format
    AlignIO.convert(
        out_fn_nucl_concat_nexus, "nexus", out_fn_nucl_concat_fasta, "fasta"
    )


# ------------------------------------------------------------------------------#
# MAIN
# ------------------------------------------------------------------------------#
def main(args):
    (
        in_dir,
        out_dir,
        fileext,
        exclude_list,
        min_seq_length,
        min_num_taxa,
        select_mode,
        verbose
    ) = unpack_input_parameters(args)
    setup_logger(verbose)

    # TO DO
    # Include function here that tests if the third-party script mafft is even available on the system

    main_odict_nucl, main_odict_prot = parse_infiles_and_extract_annos(
        in_dir, fileext, select_mode, min_seq_length
    )
    remove_duplicate_annos(main_odict_nucl, main_odict_prot, select_mode)

    remove_annos_if_below_minnumtaxa(main_odict_nucl, main_odict_prot, min_num_taxa)
    remove_orfs(main_odict_nucl, main_odict_prot)
    remove_user_defined_genes(main_odict_nucl, main_odict_prot, exclude_list, select_mode)

    save_regions_as_unaligned_matrices(main_odict_nucl)

    if not select_mode == "cds":
        multiple_sequence_alignment_nucleotide(main_odict_nucl)
    if select_mode == "cds":
        conduct_protein_alignment_and_back_translation(main_odict_prot)

    success_list = collect_successful_alignments(main_odict_nucl)
    concatenate_successful_alignments(success_list)

    log.info("end of script\n")
    quit()


# ------------------------------------------------------------------------------#
# ARGPARSE
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Author|Version: " + __version__)
    # Required
    parser.add_argument(
        "--inpd",
        "-i",
        type=str,
        required=True,
        help="path to input directory (which contains the GenBank files)",
        default="./input"
    )
    # Optional
    parser.add_argument(
        "--outd",
        "-o",
        type=str,
        required=False,
        help="(Optional) Path to output directory",
        default="./output"
    )
    parser.add_argument(
        "--selectmode",
        "-s",
        type=str,
        required=False,
        help="(Optional) Type of regions to be extracted (i.e. `cds`, `int`, or `igs`)",
        default="cds"
    )
    parser.add_argument(
        "--fileext",
        "-f",
        type=str,
        required=False,
        help="(Optional) File extension of input files",
        default=".gb"
    )
    parser.add_argument(
        "--excllist",
        "-e",
        type=list,
        required=False,
        default=["rps12"],
        help="(Optional) List of genes to be excluded"
    )
    parser.add_argument(
        "--minseqlength",
        "-l",
        type=int,
        required=False,
        help="(Optional) Minimal sequence length (in bp) below which regions will not be extracted",
        default=3
    )
    parser.add_argument(
        "--minnumtaxa",
        "-t",
        type=int,
        required=False,
        help="(Optional) Minimum number of taxa in which a region must be present to be extracted",
        default=1
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="version",
        version="%(prog)s " + __version__,
        help="(Optional) Enable verbose logging",
        default=True
    )
    args = parser.parse_args()
    main(args)
# ------------------------------------------------------------------------------#
# EOF
# ------------------------------------------------------------------------------#
