$(function(){
    $('#undo_form').submit( function(event) {
        // disable to avoid double submission
        $('#undo_submit').attr('disabled', true);
    });

    $('#sort_form').submit( function(event) {
        // disable to avoid double submission
        $('#sort_submit').attr('disabled', true);
    });

});
