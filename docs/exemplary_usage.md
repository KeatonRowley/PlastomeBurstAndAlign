#### Unpacking benchmark dataset
```
tar xzf benchmarking1.tar.gz
```

#### Exemplary usage
```
# Adjust the following line if necessary
MYSCRIPT=~/git/PlastomeBurstAndAlign/PlastomeRegionBurstAndAlign.py

cd benchmarking1/
```

##### Extract and align coding regions
```
folder_CDS=./output_CDS
mkdir -p $folder_CDS
mkdir -p $folder_CDS/01_unalign
mkdir -p $folder_CDS/02_aligned
mkdir -p $folder_CDS/02_aligned/fasta
mkdir -p $folder_CDS/02_aligned/nexus
python $MYSCRIPT -i . -o $folder_CDS -s cds 1>${folder_CDS}/${folder_CDS}.log 2>&1
mv $folder_CDS/*.unalign.fasta $folder_CDS/01_unalign
mv $folder_CDS/*.aligned.fasta $folder_CDS/02_aligned/fasta
mv $folder_CDS/*.aligned.nexus $folder_CDS/02_aligned/nexus
```

##### Extract and align introns
```
folder_INT=./output_INT
mkdir -p $folder_INT
mkdir -p $folder_INT/01_unalign
mkdir -p $folder_INT/02_aligned
mkdir -p $folder_INT/02_aligned/fasta
mkdir -p $folder_INT/02_aligned/nexus
python $MYSCRIPT -i . -o $folder_INT -s int 1>${folder_INT}/${folder_INT}.log 2>&1
mv $folder_INT/*.unalign.fasta $folder_INT/01_unalign
mv $folder_INT/*.aligned.fasta $folder_INT/02_aligned/fasta
mv $folder_INT/*.aligned.nexus $folder_INT/02_aligned/nexus
```

##### Extract and align intergenic spacers
```
folder_IGS=./output_IGS
mkdir -p $folder_IGS
mkdir -p $folder_IGS/01_unalign
mkdir -p $folder_IGS/02_aligned
mkdir -p $folder_IGS/02_aligned/fasta
mkdir -p $folder_IGS/02_aligned/nexus
python $MYSCRIPT -i . -o $folder_IGS -s igs 1>${folder_IGS}/${folder_IGS}.log 2>&1
mv $folder_IGS/*.unalign.fasta $folder_IGS/01_unalign
mv $folder_IGS/*.aligned.fasta $folder_IGS/02_aligned/fasta
mv $folder_IGS/*.aligned.nexus $folder_IGS/02_aligned/nexus
```
