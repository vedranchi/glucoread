document.addEventListener("DOMContentLoaded", () => {
  const carbsInput = document.getElementById("carbs");
  const proteinInput = document.getElementById("protein");
  const fatsInput = document.getElementById("fats");
  const caloriesInput = document.getElementById("calories");

  if (!carbsInput || !proteinInput || !fatsInput || !caloriesInput) {
    return;
  }

  const calculateCalories = () => {
    const carbs = parseFloat(carbsInput.value) || 0;
    const protein = parseFloat(proteinInput.value) || 0;
    const fats = parseFloat(fatsInput.value) || 0;
    const calories = carbs * 4 + protein * 4 + fats * 9;
    caloriesInput.value = Math.round(calories);
  };

  // Bread units are a reading of the carbs field, never an input: grams stay
  // the only thing typed and the only thing stored. The divisor comes from a
  // data attribute so the user's own unit size is used rather than a constant
  // duplicated here.
  const breadUnitsHint = document.getElementById("carbsBreadUnits");
  const gramsPerUnit = parseFloat(carbsInput.dataset.breadUnitGrams);
  const defaultHint = breadUnitsHint ? breadUnitsHint.textContent.trim() : "";

  const showBreadUnits = () => {
    if (!breadUnitsHint || !(gramsPerUnit > 0)) return;

    const carbs = parseFloat(carbsInput.value);
    if (!Number.isFinite(carbs) || carbs <= 0) {
      breadUnitsHint.textContent = defaultHint;
      return;
    }

    const units = Math.round((carbs / gramsPerUnit) * 10) / 10;
    breadUnitsHint.textContent =
      units + " BU at " + gramsPerUnit + " g each";
  };

  carbsInput.addEventListener("input", showBreadUnits);
  carbsInput.addEventListener("input", calculateCalories);
  proteinInput.addEventListener("input", calculateCalories);
  fatsInput.addEventListener("input", calculateCalories);

  // Only derive calories on load if there is actually something to derive them
  // from. The macro fields are nullable, so editing a meal that stored calories
  // but no macros arrives here with all three blank — recomputing would put 0
  // in the readonly field and overwrite the saved value on save.
  const hasMacros = [carbsInput, proteinInput, fatsInput].some(
    (input) => input.value.trim() !== ""
  );
  if (hasMacros) {
    calculateCalories();
  }
  showBreadUnits();
});
