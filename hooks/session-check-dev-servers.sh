#!/usr/bin/env bash
# Check for running dev servers and warn if there are too many

threshold=2

# Find node processes running dev servers
declare -a servers=()

while IFS= read -r line; do
    [ -z "$line" ] && continue
    pid=$(echo "$line" | awk '{print $2}')
    cmd=$(echo "$line" | awk '{for(i=11;i<=NF;i++) printf "%s ", $i; print ""}')

    # Only match dev server patterns
    if ! echo "$cmd" | grep -qE '(astro|next|vite|webpack).*(dev|start)|--port [0-9]+'; then
        continue
    fi

    # Skip child workers
    if echo "$cmd" | grep -qE 'start-server\.js|npx-cli\.js|npm-cli\.js'; then
        continue
    fi

    port="?"
    if [[ "$cmd" =~ --port[[:space:]]+([0-9]+) ]]; then
        port="${BASH_REMATCH[1]}"
    elif [[ "$cmd" =~ -p[[:space:]]+([0-9]+) ]]; then
        port="${BASH_REMATCH[1]}"
    fi

    project="unknown"
    if [[ "$cmd" =~ projects/([^/]+(/sites/[^/]+)?) ]]; then
        project="${BASH_REMATCH[1]}"
    fi

    framework="node"
    if echo "$cmd" | grep -qi 'astro'; then
        framework="Astro"
    elif echo "$cmd" | grep -qi 'next'; then
        framework="Next.js"
    elif echo "$cmd" | grep -qi 'vite'; then
        framework="Vite"
    fi

    servers+=("$port|$project|$framework|$pid")
done < <(ps aux 2>/dev/null | grep '[n]ode' || true)

# Deduplicate by port
declare -A seen_ports
declare -a unique=()
for entry in "${servers[@]}"; do
    port=$(echo "$entry" | cut -d'|' -f1)
    if [ -z "${seen_ports[$port]}" ]; then
        seen_ports[$port]=1
        unique+=("$entry")
    fi
done

count=${#unique[@]}

if [ "$count" -gt "$threshold" ]; then
    list=""
    for entry in "${unique[@]}"; do
        port=$(echo "$entry" | cut -d'|' -f1)
        project=$(echo "$entry" | cut -d'|' -f2)
        framework=$(echo "$entry" | cut -d'|' -f3)
        list+="  :$port $project ($framework)"$'\n'
    done
    printf "[warn] %d dev servers running:\n%s  Use 'ps aux | grep node' to manage them.\n" "$count" "$list"
fi
