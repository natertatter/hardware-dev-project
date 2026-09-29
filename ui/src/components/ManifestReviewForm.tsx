"use client";

import type { ComponentType, PinType } from "@/types/schemas";
import type { ComponentManifest } from "@/types/schemas";
import {
  PIN_TYPES,
  addPin,
  localCommitErrors,
  removePin,
  updatePin,
  withComponentId,
  withConstraint,
  withI2cAddress,
  withName,
  withPower,
  withType,
  type ExtractionIssue,
} from "@/lib/manifestReview";

const COMPONENT_TYPES: ComponentType[] = [
  "MCU",
  "SENSOR",
  "MOTOR_DRIVER",
  "ACTUATOR",
  "PASSIVE",
];

interface ManifestReviewFormProps {
  manifest: ComponentManifest;
  issues: ExtractionIssue[];
  note: string;
  extractionSource: string;
  saving: boolean;
  error: string | null;
  onChange: (manifest: ComponentManifest) => void;
  onSave: () => void;
  onDiscard: () => void;
}

export function ManifestReviewForm({
  manifest,
  issues,
  note,
  extractionSource,
  saving,
  error,
  onChange,
  onSave,
  onDiscard,
}: ManifestReviewFormProps) {
  const localErrors = localCommitErrors(manifest);
  const constraints = manifest.operational_constraints;

  return (
    <form
      className="datasheet-review"
      onSubmit={(e) => {
        e.preventDefault();
        onSave();
      }}
    >
      <p className="datasheet-review__note">
        {note} Source: {extractionSource}. Nothing is added to the catalog until you save.
      </p>
      {issues.length > 0 && (
        <ul className="datasheet-review__issues">
          {issues.map((issue) => (
            <li
              key={`${issue.code}-${issue.field ?? ""}-${issue.message}`}
              className={
                issue.severity === "error"
                  ? "datasheet-review__issue--error"
                  : "datasheet-review__issue--warning"
              }
            >
              {issue.message}
            </li>
          ))}
        </ul>
      )}
      <label className="datasheet-review__label">
        Name
        <input
          className="datasheet-review__input"
          value={manifest.name}
          onChange={(e) => onChange(withName(manifest, e.target.value))}
        />
      </label>
      <label className="datasheet-review__label">
        Component id
        <input
          className="datasheet-review__input"
          value={manifest.component_id}
          onChange={(e) => onChange(withComponentId(manifest, e.target.value))}
        />
      </label>
      <label className="datasheet-review__label">
        Type
        <select
          className="datasheet-review__input"
          value={manifest.type}
          onChange={(e) => onChange(withType(manifest, e.target.value as ComponentType))}
        >
          {COMPONENT_TYPES.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
      </label>
      <div className="datasheet-review__grid">
        <NumberField
          label="Min V"
          value={manifest.power_requirements.min_operating_voltage}
          onChange={(value) => onChange(withPower(manifest, "min_operating_voltage", value))}
        />
        <NumberField
          label="Max V"
          value={manifest.power_requirements.max_operating_voltage}
          onChange={(value) => onChange(withPower(manifest, "max_operating_voltage", value))}
        />
        <NumberField
          label="Logic V"
          value={manifest.power_requirements.logic_level_voltage}
          onChange={(value) => onChange(withPower(manifest, "logic_level_voltage", value))}
        />
        <NumberField
          label="Max mA"
          value={manifest.power_requirements.max_current_draw_ma}
          onChange={(value) => onChange(withPower(manifest, "max_current_draw_ma", value))}
        />
      </div>
      <label className="datasheet-review__label">
        I2C address
        <input
          className="datasheet-review__input"
          value={manifest.default_i2c_address ?? ""}
          placeholder="0x76"
          onChange={(e) => onChange(withI2cAddress(manifest, e.target.value))}
        />
      </label>
      <div className="datasheet-review__grid">
        <OptionalNumberField
          label="Power-on ms"
          value={constraints?.power_on_delay_ms}
          onChange={(value) => onChange(withConstraint(manifest, "power_on_delay_ms", value))}
        />
        <OptionalNumberField
          label="Conversion ms"
          value={constraints?.conversion_time_ms}
          onChange={(value) => onChange(withConstraint(manifest, "conversion_time_ms", value))}
        />
      </div>
      <p className="datasheet-review__pins-title">Pins</p>
      {manifest.pins.map((pin, index) => (
        <div key={index} className="datasheet-review__pin">
          <input
            className="datasheet-review__input"
            aria-label={`Pin ${index + 1} id`}
            value={pin.pin_id}
            onChange={(e) => onChange(updatePin(manifest, index, { pin_id: e.target.value }))}
          />
          <select
            className="datasheet-review__input"
            aria-label={`Pin ${index + 1} type`}
            value={pin.pin_type}
            onChange={(e) =>
              onChange(updatePin(manifest, index, { pin_type: e.target.value as PinType }))
            }
          >
            {PIN_TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="editor-shell__btn editor-shell__btn--compact"
            onClick={() => onChange(removePin(manifest, index))}
          >
            Remove
          </button>
        </div>
      ))}
      <button
        type="button"
        className="editor-shell__btn editor-shell__btn--compact"
        onClick={() => onChange(addPin(manifest))}
      >
        Add pin
      </button>
      {localErrors.map((message) => (
        <p key={message} className="panel-card__message panel-card__message--error">
          {message}
        </p>
      ))}
      {error && <p className="panel-card__message panel-card__message--error">{error}</p>}
      <div className="datasheet-review__actions">
        <button
          type="submit"
          className="editor-shell__btn editor-shell__btn--approve"
          disabled={saving || localErrors.length > 0}
        >
          {saving ? "Saving…" : "Save to catalog"}
        </button>
        <button
          type="button"
          className="editor-shell__btn editor-shell__btn--compact"
          onClick={onDiscard}
          disabled={saving}
        >
          Discard
        </button>
      </div>
    </form>
  );
}

function NumberField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="datasheet-review__label">
      {label}
      <input
        className="datasheet-review__input"
        type="number"
        step="any"
        value={value}
        onChange={(e) => {
          const next = Number(e.target.value);
          if (Number.isFinite(next)) {
            onChange(next);
          }
        }}
      />
    </label>
  );
}

function OptionalNumberField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number | null | undefined;
  onChange: (value: number | null) => void;
}) {
  return (
    <label className="datasheet-review__label">
      {label}
      <input
        className="datasheet-review__input"
        type="number"
        step="any"
        value={value ?? ""}
        onChange={(e) => {
          if (e.target.value.trim() === "") {
            onChange(null);
            return;
          }
          const next = Number(e.target.value);
          if (Number.isFinite(next)) {
            onChange(next);
          }
        }}
      />
    </label>
  );
}
