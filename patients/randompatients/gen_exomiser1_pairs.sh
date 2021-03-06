#!/usr/bin/env bash
usage="usage: $0 source_loc num_pairs [-R]"

#test for help flag
if [ $1 == '-h' ]
then
    echo "$usage"  
    exit 1
fi
#ensure positional arguments are present
if [ $# -lt 2 ]; then
    echo "$usage"
    exit 1
fi

set -eu
set -o pipefail
# Use date and time as signature for generated data
sig=EX1_PAIRS_`date +%F-%H-%M-%S`
#sge stuff
memory=10G
processors=1
logdir=~/sge_logs/gen_exomise/$sig/
mkdir -pv $logdir
if [ $# -eq 3 ] && [ $3 == '-R' ]; then
    out=/dupa-filer/talf/matchingsim/patients/"$sig"R
else
    out=/dupa-filer/talf/matchingsim/patients/$sig
fi
data=/dupa-filer/talf/matchingsim/patients

delay=15

#location of files given first, number of files to generate is given as second argument
loc=$1
num=$2

mkdir -pv $out
#run patient pair generator
if [ $# -eq 3 ] && [ $3 == '-R' ]; then
    python $data/randompatients/generate_patient_pairs.py $data --vcf_path $loc -N $num $out -I AR
else
    python $data/randompatients/generate_patient_pairs.py $data --vcf_path $loc -N $num $out -I AD
fi

#create a script and dispatch exomizer job
cat > "$out/rerun.sh" <<EOF
for file in $out/*.vcf
do
    f=\`echo \$file | rev | cut -d '/' -f1 | rev | cut -d '.' -f1\`
    #resubmit script only if the required file doesn't already exist
    if [ ! -f "$out"/\$f.ezr ]
    then
        qsub -S /bin/sh "$out/scripts/dispatch_\$f.sh"
        sleep $delay
    fi
done
EOF

chmod +x "$out/rerun.sh"

mkdir -pv $out/scripts
for file in $out/*.vcf; do
    #create a bash script
    #get only ending to name script
    f=`echo $file | rev | cut -d '/' -f1 | rev | cut -d '.' -f1`
    script="$out/scripts/dispatch_$f.sh"   
    if [ $# -eq 3 ] && [ $3 == '-R' ]; then
        cat > "$script" <<EOF
#!/usr/bin/env bash
#$ -V
#$ -N "$f"
#$ -pe parallel "$processors"
#$ -l h_vmem="$memory"
#$ -e $logdir
#$ -o $logdir

set -eu
set -o pipefail
temp=\$TMPDIR/$f.ezr

#only unzip if the unziped file doesn't already exist (i.e. only unzip on first run)
if [ ! -f "$out"/$f.vcf ]
then
    gunzip $out/$f.vcf.gz
fi
java -Xmx1900m -Xms1000m -jar /data/Exomiser/Exomizer.jar --db_url jdbc:postgresql://supa01.biolab.sandbox/nsfpalizer -D /data/Exomiser/ucsc.ser -I AR -F 1 --hpo_ids `cat $out/"$f"_hpo.txt` -v $out/$f.vcf --vcf_output -o \$temp -P

mv -v \$temp $out/$f.ezr.temp
mv -v $out/$f.ezr.temp $out/$f.ezr
EOF
    else
        cat > "$script" <<EOF
#!/usr/bin/env bash
#$ -V
#$ -N "$f"
#$ -pe parallel "$processors"
#$ -l h_vmem="$memory"
#$ -e $logdir
#$ -o $logdir

set -eu
set -o pipefail
temp=\$TMPDIR/$f.ezr

#only unzip if the unziped file doesn't already exist (i.e. only unzip on first run)
if [ ! -f "$out"/$f.vcf ]
then
    gunzip $out/$f.vcf.gz
fi
java -Xmx1900m -Xms1000m -jar /data/Exomiser/Exomizer.jar --db_url jdbc:postgresql://supa01.biolab.sandbox/nsfpalizer -D /data/Exomiser/ucsc.ser -I AD -F 1 --hpo_ids `cat $out/"$f"_hpo.txt` -v $out/$f.vcf --vcf_output -o \$temp -P

mv -v \$temp $out/$f.ezr.temp
mv -v $out/$f.ezr.temp $out/$f.ezr
EOF
    fi
    #Submit
    qsub -S /bin/sh "$script"
    #wait so we don't overload cluster
    sleep $delay
done

