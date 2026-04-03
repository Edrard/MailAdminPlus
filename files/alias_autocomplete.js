/* Autocomplete for Alias Destinations */
$(document).ready(function () {
    var $textarea = $('textarea[name="destinations"]');
    if ($textarea.length === 0) return;

    // Create dropdown wrapper
    var $wrapper = $('<div class="autocomplete-wrapper" style="position:relative;"></div>');
    $textarea.wrap($wrapper);

    var $dropdown = $('<ul class="autocomplete-dropdown" style="display:none; position:absolute; z-index:1000; background:#fff; border:1px solid #ccc; list-style:none; margin:0; padding:0; width:100%; max-height:150px; overflow-y:auto; box-shadow:0 4px 6px rgba(0,0,0,0.1);"></ul>');
    $textarea.after($dropdown);

    var currentFocus = -1;

    $textarea.on('input keyup', function (e) {
        // Navigation keys handled separately
        if ([38, 40, 13].indexOf(e.keyCode) > -1) return;

        var val = this.value;
        var cursor = this.selectionStart;
        var textBeforeCursor = val.substring(0, cursor);

        // Find the current search term separated by comma or space
        var parts = textBeforeCursor.split(/[\s,]+/);
        var currentWord = parts[parts.length - 1];

        if (currentWord.length < 2) {
            $dropdown.hide();
            return;
        }

        $.getJSON(iRedAdminHomePath + '/api/search_destinations', { q: currentWord }, function (data) {
            $dropdown.empty();
            if (data && data.length > 0) {
                currentFocus = -1;
                $.each(data, function (index, item) {
                    var $li = $('<li style="padding:8px 10px; cursor:pointer; border-bottom:1px solid #eee;">' + item + '</li>');

                    $li.hover(function () {
                        $(this).css('background-color', '#f0f0f0');
                    }, function () {
                        $(this).css('background-color', '#fff');
                    });

                    $li.click(function () {
                        insertCompletion(item);
                    });

                    $dropdown.append($li);
                });
                $dropdown.show();
            } else {
                $dropdown.hide();
            }
        });
    });

    // Keyboard navigation
    $textarea.on('keydown', function (e) {
        if (!$dropdown.is(':visible')) return;
        var items = $dropdown.find('li');
        if (items.length === 0) return;

        if (e.keyCode === 40) { // Down
            currentFocus++;
            setActive(items);
            e.preventDefault();
        } else if (e.keyCode === 38) { // Up
            currentFocus--;
            setActive(items);
            e.preventDefault();
        } else if (e.keyCode === 13) { // Enter
            if (currentFocus > -1) {
                items.eq(currentFocus).click();
                e.preventDefault();
            }
        }
    });

    function setActive(items) {
        items.css('background-color', '#fff');
        if (currentFocus >= items.length) currentFocus = 0;
        if (currentFocus < 0) currentFocus = (items.length - 1);
        items.eq(currentFocus).css('background-color', '#e0e0e0');
    }

    function insertCompletion(item) {
        var val = $textarea.val();
        var cursor = $textarea[0].selectionStart;

        var textBefore = val.substring(0, cursor);
        var textAfter = val.substring(cursor);

        var lastPuncIndex = Math.max(textBefore.lastIndexOf(','), textBefore.lastIndexOf(' '));
        var prefix = textBefore.substring(0, lastPuncIndex + 1);

        // Add completion and format nicely
        var newTextBefore = prefix + (prefix.endsWith(',') && !prefix.endsWith(', ') ? ' ' : '') + item + ', ';

        $textarea.val(newTextBefore + textAfter);
        $textarea[0].setSelectionRange(newTextBefore.length, newTextBefore.length);
        $dropdown.hide();
        $textarea.focus();
    }

    // Hide on click outside
    $(document).click(function (e) {
        if (!$(e.target).closest('.autocomplete-wrapper').length) {
            $dropdown.hide();
        }
    });
});
