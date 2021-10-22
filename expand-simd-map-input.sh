#!/bin/bash
# SPDX-License-Identifier: LGPL-3-or-later
# See Notices.txt for copyright information

# utility script for expanding input type annotations for SimdMap methods.
# not actually needed anymore, but I thought I'd commit it in case anyone
# finds it useful.

mapfile lines < src/ieee754/part/util.pyi

defs=()
def=""
LOOKING_FOR_DEF=0
PARSING_BODY=1
((state = LOOKING_FOR_DEF))

# split into list of python method definitions
for line in "${lines[@]}"; do
    if ((state == LOOKING_FOR_DEF)); then
        if [[ "$line" =~ ^' '*'def ' ]]; then
            ((state = PARSING_BODY))
        fi
        def+="$line"
    elif [[ "$line" =~ ^' '*'@' ]]; then
        defs+=("$def")
        def="$line"
        ((state = LOOKING_FOR_DEF))
    elif [[ "$line" =~ ^' '*'def ' ]]; then
        defs+=("$def")
        def="$line"
    else
        def+="$line"
    fi
done
if [[ "$def" != "" ]]; then
    defs+=("$def")
fi

# expand all occurrences of _SimdMapInput[_T...]
((working = 1))
while ((working)); do
    ((working = 0))
    old_defs=("${defs[@]}")
    defs=()
    for def in "${old_defs[@]}"; do
        if [[ "$def" =~ ^(.*)'Optional[_SimdMapInput['(_T[0-9]*)']]'(.*)$ ]] ||
                [[ "$a" =~ ^(.*)'_SimdMapInput['(_T[0-9]*)']'(.*)$ ]]; then
            ((working = 1))
            defs+=("${BASH_REMATCH[1]}SimdMap[${BASH_REMATCH[2]}]${BASH_REMATCH[3]}")
            defs+=("${BASH_REMATCH[1]}Mapping[_ElWid, Optional[${BASH_REMATCH[2]}]]${BASH_REMATCH[3]}")
            defs+=("${BASH_REMATCH[1]}Optional[${BASH_REMATCH[2]}]${BASH_REMATCH[3]}")
        else
            defs+=("$def")
        fi
    done
done

printf "%s" "${defs[@]}" > out.txt
