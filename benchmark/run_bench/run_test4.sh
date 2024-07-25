#!/bin/bash

# Initialize CSV file with headers
echo "index,filename,n_features,n_constraints,execution_time,result,clif_gen_time,clif_ast_time,bridge_solve_time,code_gen_time,generic_csp_model_time,concrete_csp_model_time" > output_detailed_$1.csv

# Maximum number of parallel requests
n=16
# Function to process a file
process_file() {
    filename=$1
    index=$3

    # Read file content
    uvl_content=$(cat "$filename")

    # Create JSON payload
    json_payload=$(jq -n \
                      --arg input "uvl" \
                      --arg model "$uvl_content" \
                      --arg operation "sat" \
                      --arg solver "$2" \
                      '{data: {input: $input, model: $model, query: {operation: $operation, solver: $solver}}}')

    # Send POST request and measure its time
    #start_time=$(date +%s%N)
    response=$(curl -s -w "%{http_code}" -o temp$index.json -X POST -H "Content-Type: application/json" -d "$json_payload" http://localhost:5000/query)
    #end_time=$(date +%s%N)
    #execution_time=$((end_time - start_time))
    execution_time=$(jq -r '.statistics.total_time' temp$index.json)    

    # Check if the request was successful
    if [ "$response" -eq 200 ]; then
        # Extract result from the response JSON
        result=$(jq -r '.data.content' temp$index.json)
	clif_gen_time=$(jq -r '.statistics.clif_gen_time' temp$index.json)
	clif_ast_time=$(jq -r '.statistics.clif_ast_time' temp$index.json)
	bridge_solve_time=$(jq -r '.statistics.bridge_solve_time' temp$index.json)
	code_gen_time=$(jq -r '.statistics.code_gen_time' temp$index.json)
	generic_csp_model_time=$(jq -r '.statistics.generic_csp_model_time' temp$index.json)
	concrete_csp_model_time=$(jq -r '.statistics.concrete_csp_model_time' temp$index.json)
	n_features=$(jq -r '.statistics.n_features' temp$index.json)
	n_constraints=$(jq -r '.statistics.n_constraints' temp$index.json)
        # Write data to the CSV file
        echo "$index,$filename,$n_features,$n_constraints,$execution_time,$result,$clif_gen_time,$clif_ast_time,$bridge_solve_time,$code_gen_time,$generic_csp_model_time,$concrete_csp_model_time" >> output_detailed_$2.csv
        # Echo success message
        echo "Request for $filename was successful. Execution time: $execution_time nanoseconds."
    else
        # Echo failure message
        echo "Request for $filename failed with HTTP status code $response."
    fi
    global_idx=$((global_idx++))
    if [ -f "temp$index.json" ] ; then    
    	rm temp$index.json
    fi
}

export -f process_file

# Find .uvl files, pass them to process_file in parallel
find .. -name "*.uvl" | xargs -I {} -P $n --process-slot-var=index bash -c 'process_file "$@" "$index"' _ {} $1
