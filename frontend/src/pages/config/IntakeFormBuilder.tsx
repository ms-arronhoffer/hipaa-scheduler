import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Container from "@cloudscape-design/components/container";
import Header from "@cloudscape-design/components/header";
import Button from "@cloudscape-design/components/button";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Box from "@cloudscape-design/components/box";
import Spinner from "@cloudscape-design/components/spinner";
import ColumnLayout from "@cloudscape-design/components/column-layout";
import Input from "@cloudscape-design/components/input";
import FormField from "@cloudscape-design/components/form-field";
import Select, { SelectProps } from "@cloudscape-design/components/select";
import Toggle from "@cloudscape-design/components/toggle";
import Textarea from "@cloudscape-design/components/textarea";
import PageHeader from "../../components/layout/PageHeader";
import { intakeFormsApi } from "../../api";
import { useFlash } from "../../context/FlashbarContext";

// Intake form definition matches the plan spec:
// {version, pages:[{sections:[{fields:[{key,type,label,required,options,validators,showIf}]}]}]}
interface Field {
  key: string;
  type: string;
  label: string;
  required?: boolean;
  options?: string[];
  showIf?: string;
}
interface Section { fields: Field[] }
interface Page { sections: Section[] }
interface Definition {
  version: number;
  pages: Page[];
}

const TYPE_OPTIONS: SelectProps.Option[] = [
  { label: "Text", value: "text" },
  { label: "Textarea", value: "textarea" },
  { label: "Date", value: "date" },
  { label: "Select", value: "select" },
  { label: "Multi-select", value: "multi" },
  { label: "Signature", value: "signature" },
  { label: "Scale 1–10", value: "scale" },
  { label: "File upload", value: "file" },
  { label: "Consent block", value: "consent-block" },
];

interface FormRecord {
  id: string;
  name: string;
  version: number;
  definition: Definition;
}

export default function IntakeFormBuilder() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const { push } = useFlash();
  const [form, setForm] = useState<FormRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!id) return;
    intakeFormsApi.get(id)
      .then((f) => setForm(f as FormRecord))
      .catch(() => push({ type: "error", content: "Failed to load form" }))
      .finally(() => setLoading(false));
  }, [id, push]);

  function updateDef(mut: (d: Definition) => void) {
    if (!form) return;
    const next: Definition = JSON.parse(JSON.stringify(form.definition));
    mut(next);
    setForm({ ...form, definition: next });
  }

  function addField(pageIdx: number, sectionIdx: number) {
    updateDef((d) => {
      d.pages[pageIdx].sections[sectionIdx].fields.push({
        key: `field_${Date.now()}`,
        type: "text",
        label: "New field",
        required: false,
      });
    });
  }
  function removeField(pageIdx: number, sectionIdx: number, fieldIdx: number) {
    updateDef((d) => { d.pages[pageIdx].sections[sectionIdx].fields.splice(fieldIdx, 1); });
  }
  function updateField(pageIdx: number, sectionIdx: number, fieldIdx: number, patch: Partial<Field>) {
    updateDef((d) => { Object.assign(d.pages[pageIdx].sections[sectionIdx].fields[fieldIdx], patch); });
  }
  function addSection(pageIdx: number) {
    updateDef((d) => { d.pages[pageIdx].sections.push({ fields: [] }); });
  }
  function addPage() {
    updateDef((d) => { d.pages.push({ sections: [{ fields: [] }] }); });
  }

  async function save() {
    if (!form) return;
    setSaving(true);
    try {
      await intakeFormsApi.update(form.id, { name: form.name, definition: form.definition });
      push({ type: "success", content: "Form saved" });
    } catch {
      push({ type: "error", content: "Save failed" });
    } finally { setSaving(false); }
  }

  if (loading || !form) {
    return <PageHeader title="Intake form"><Box textAlign="center" padding="xxl"><Spinner size="large" /></Box></PageHeader>;
  }

  return (
    <PageHeader
      title={form.name}
      description={`Version ${form.version} · ${form.definition.pages.length} page(s)`}
      actions={
        <SpaceBetween direction="horizontal" size="xs">
          <Button onClick={() => nav("/config/intake-forms")}>Back</Button>
          <Button variant="primary" loading={saving} onClick={save}>Save</Button>
        </SpaceBetween>
      }
    >
      <SpaceBetween size="l">
        <Container header={<Header variant="h2">Form settings</Header>}>
          <FormField label="Name">
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.detail.value })} />
          </FormField>
        </Container>

        {form.definition.pages.map((page, pIdx) => (
          <Container
            key={pIdx}
            header={
              <Header
                variant="h2"
                actions={<Button onClick={() => addSection(pIdx)}>Add section</Button>}
              >
                Page {pIdx + 1}
              </Header>
            }
          >
            <SpaceBetween size="l">
              {page.sections.map((section, sIdx) => (
                <Container
                  key={sIdx}
                  variant="stacked"
                  header={
                    <Header
                      variant="h3"
                      actions={<Button onClick={() => addField(pIdx, sIdx)}>Add field</Button>}
                    >
                      Section {sIdx + 1}
                    </Header>
                  }
                >
                  <SpaceBetween size="m">
                    {section.fields.length === 0 && <Box color="text-body-secondary">No fields yet.</Box>}
                    {section.fields.map((f, fIdx) => (
                      <Container key={fIdx} variant="stacked">
                        <SpaceBetween size="s">
                          <ColumnLayout columns={3}>
                            <FormField label="Key" description="Machine identifier">
                              <Input value={f.key} onChange={(e) => updateField(pIdx, sIdx, fIdx, { key: e.detail.value })} />
                            </FormField>
                            <FormField label="Label">
                              <Input value={f.label} onChange={(e) => updateField(pIdx, sIdx, fIdx, { label: e.detail.value })} />
                            </FormField>
                            <FormField label="Type">
                              <Select
                                selectedOption={TYPE_OPTIONS.find((o) => o.value === f.type) ?? TYPE_OPTIONS[0]}
                                options={TYPE_OPTIONS}
                                onChange={(e) => updateField(pIdx, sIdx, fIdx, { type: e.detail.selectedOption.value! })}
                              />
                            </FormField>
                          </ColumnLayout>
                          {(f.type === "select" || f.type === "multi") && (
                            <FormField label="Options" description="One per line">
                              <Textarea
                                value={(f.options ?? []).join("\n")}
                                onChange={(e) => updateField(pIdx, sIdx, fIdx, { options: e.detail.value.split("\n").filter(Boolean) })}
                              />
                            </FormField>
                          )}
                          <FormField label="Show if" description="Expression, e.g. answers.smoker == 'yes'">
                            <Input value={f.showIf ?? ""} onChange={(e) => updateField(pIdx, sIdx, fIdx, { showIf: e.detail.value })} />
                          </FormField>
                          <SpaceBetween direction="horizontal" size="s">
                            <Toggle checked={f.required ?? false} onChange={(e) => updateField(pIdx, sIdx, fIdx, { required: e.detail.checked })}>Required</Toggle>
                            <Button iconName="remove" onClick={() => removeField(pIdx, sIdx, fIdx)}>Remove field</Button>
                          </SpaceBetween>
                        </SpaceBetween>
                      </Container>
                    ))}
                  </SpaceBetween>
                </Container>
              ))}
            </SpaceBetween>
          </Container>
        ))}

        <Button onClick={addPage} iconName="add-plus">Add page</Button>
      </SpaceBetween>
    </PageHeader>
  );
}
