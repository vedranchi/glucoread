// Image preview functionality
const imageInput = document.getElementById('id_image');
const imagePreview = document.getElementById('profileImagePreview');

if (imageInput) {
    imageInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function(e) {
                imagePreview.src = e.target.result;
            }
            reader.readAsDataURL(file);
        }
    });
}

// Reset the target band to the standard one. This only fills the inputs --
// nothing is stored until the form is submitted, so the reset is undoable and
// the page keeps its all-or-nothing save. The values come from data
// attributes rather than being written here, because they depend on the
// user's unit and the conversion belongs on the server.
const resetTargets = document.querySelector('[data-reset-targets]');

if (resetTargets) {
    resetTargets.addEventListener('click', function () {
        const low = document.getElementById('id_target_low');
        const high = document.getElementById('id_target_high');
        if (!low || !high) return;

        low.value = this.dataset.targetLow;
        high.value = this.dataset.targetHigh;

        // Clear the browser's own validation state, which a previous rejected
        // submit may have left on the fields.
        [low, high].forEach(function (field) {
            field.dispatchEvent(new Event('input', { bubbles: true }));
        });
        low.focus();
    });
}
