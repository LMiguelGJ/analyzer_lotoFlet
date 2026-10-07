import type { GameRulesView } from "../lib/game-rules";
import { CLASSIC_SETTLEMENT_LABELS, classicRulesMoney, gameSettingsSourceLabel, profileRulesMoney, profileSettlementLabel } from "../lib/game-rules";

/** Common layout, separate native contracts. No payout calculation or editable state. */
export function GameRulesSummary({ view }: { view: GameRulesView }) {
  if (view.kind === "classic") {
    const { rules } = view;
    return <div role="group" className="space-y-3" aria-label="Resumen de reglas clásicas">
      <p className="field-help">Reglas clásicas · {view.draft ? "Borrador; no es una revisión de perfil" : "Lectura efectiva"}. Origen: {view.provenance}.</p>
      <dl className="data-list">
        {rules.name !== undefined && <><dt>Sorteo</dt><dd>{rules.name || "Sin nombre"}</dd></>}
        <dt>Números posibles</dt><dd>{rules.numbers || "Sin definir"}</dd>
        <dt>Posiciones por sorteo</dt><dd>{rules.positions || "Sin definir"}</dd>
        <dt>Repeticiones</dt><dd>{rules.allows_repeats === undefined ? "No informadas por este contrato" : rules.allows_repeats ? "Permitidas" : "No permitidas"}</dd>
        <dt>Premios por posición</dt><dd><ol className="space-y-1">{rules.prizes.map((prize, index) => <li key={index}>Posición {index + 1}: {classicRulesMoney(prize)} por cada RD$1 apostado.</li>)}</ol></dd>
        <dt>Apuesta mínima por número</dt><dd>{classicRulesMoney(rules.minimum_stake)}</dd>
        <dt>Moneda y escala</dt><dd>DOP · pesos enteros (escala 0)</dd>
        <dt>Liquidación</dt><dd>{view.settlementContract === "historical-unreported"
          ? "El contrato histórico no expone una selección de liquidación."
          : view.settlement ? `${view.settlement}: ${CLASSIC_SETTLEMENT_LABELS[view.settlement]}` : "all: sumar premios · best: primera posición coincidente por número, no el pago máximo."}</dd>
      </dl>
      <details><summary className="disclosure-summary text-sm">Origen y campos clásicos</summary><div className="space-y-2 pt-2">
        <p>Origen de ajustes: {gameSettingsSourceLabel(view.source)}.</p>
        <p>Esta lectura clásica no proporciona ID, revisión ni huella de perfil.</p>
        <pre className="overflow-x-auto whitespace-pre-wrap break-all text-sm">{JSON.stringify(rules, null, 2)}</pre>
      </div></details>
    </div>;
  }

  const { profile, profile_sha256, profile_execution, execution_supported } = view.listing;
  return <div role="group" className="space-y-3" aria-label="Resumen de reglas de perfil">
    <p className="field-help">Perfil versionado · solo lectura. Origen: {view.provenance}. No usa el borrador clásico de Ajustes.</p>
    <dl className="data-list">
      <dt>ID del perfil</dt><dd className="break-all">{profile.profile_id}</dd>
      <dt>Revisión</dt><dd>{profile.revision}</dd>
      <dt>Versión del esquema</dt><dd>{profile.schema_version}</dd>
      <dt>Huella SHA-256 del perfil</dt><dd className="break-all font-mono">{profile_sha256}</dd>
      <dt>Números posibles</dt><dd>{profile.universe_size}</dd>
      <dt>Posiciones por sorteo</dt><dd>{profile.positions}</dd>
      <dt>Repeticiones</dt><dd>{profile.allows_repeats ? "Permitidas" : "No permitidas"}</dd>
      <dt>Premios por posición</dt><dd><ol className="space-y-1">{profile.multipliers.map((prize, index) => <li key={index}>Posición {index + 1}: multiplicador exacto {prize.numerator}/{prize.denominator} de la apuesta; no es un importe fijo.</li>)}</ol></dd>
      <dt>Moneda y escala</dt><dd>{profile.currency} · escala {profile.scale}</dd>
      <dt>Apuesta mínima por número</dt><dd>{profileRulesMoney(profile, profile.minimum_stake)}</dd>
      <dt>Apuesta máxima por número</dt><dd>{profileRulesMoney(profile, profile.maximum_stake)}</dd>
      <dt>Incremento de apuesta</dt><dd>{profileRulesMoney(profile, profile.stake_increment)}</dd>
      <dt>Cobertura máxima</dt><dd>{profile.max_coverage} números</dd>
      <dt>Exposición máxima</dt><dd>{profileRulesMoney(profile, profile.max_exposure)}</dd>
      <dt>Regla nativa de best</dt><dd>{profile.best_rule} · {profileSettlementLabel(profile, "best")}</dd>
      <dt>Liquidación</dt><dd>{view.settlement ? `${view.settlement}: ${profileSettlementLabel(profile, view.settlement)}` : "Sin selección de sesión en esta lectura"}</dd>
      <dt>Liquidaciones anunciadas por el servidor</dt><dd>{profile_execution.settlements.join(" · ") || "Ninguna"}</dd>
      <dt>Disponibilidad de ejecución</dt><dd>{execution_supported ? "Ejecución soportada" : "Ejecución no soportada"} · {profile_execution.ready ? "Perfil preparado" : "Perfil no preparado"}</dd>
    </dl>
    <details><summary className="disclosure-summary text-sm">Campos nativos del perfil y capacidades</summary><div className="space-y-2 pt-2">
      <p>Los importes nativos son unidades enteras escaladas de {profile.currency}. Se conservan debajo sin conversión ni redondeo.</p>
      <pre className="overflow-x-auto whitespace-pre-wrap break-all text-sm">{JSON.stringify(view.listing, null, 2)}</pre>
    </div></details>
  </div>;
}
