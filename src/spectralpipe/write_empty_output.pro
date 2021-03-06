pro write_empty_output, sourcename, scans
    compile_opt idl2

    ; nan out all the channel data for future retrieval
    for ii=0,n_elements(scans)-1 do begin
       flag, scans[0], id='empty_'+sourcename
    endfor

    ; ignore any flags here - show firts scan warts and all
    gettp, scans[0]

    write_output, sourcename, scans
    make_plot, sourcename
end
