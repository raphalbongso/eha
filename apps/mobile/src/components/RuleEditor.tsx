/** Rule editor component for creating/editing email matching rules. */

import React, { useState } from 'react';
import {
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';

import type { ConditionType, RuleCondition, RuleConditions } from '../types';

interface RuleEditorProps {
  initialName?: string;
  initialConditions?: RuleConditions;
  initialActive?: boolean;
  onSave: (name: string, conditions: RuleConditions, isActive: boolean) => void;
  onCancel: () => void;
}

const CONDITION_TYPES: { type: ConditionType; label: string }[] = [
  { type: 'from_contains', label: 'From contains' },
  { type: 'subject_contains', label: 'Subject contains' },
  { type: 'has_attachment', label: 'Has attachment' },
  { type: 'label', label: 'Gmail label' },
  { type: 'body_keywords', label: 'Body keywords' },
];

export function RuleEditor({
  initialName = '',
  initialConditions,
  initialActive = true,
  onSave,
  onCancel,
}: RuleEditorProps) {
  const [name, setName] = useState(initialName);
  const [logic, setLogic] = useState<'AND' | 'OR'>(
    initialConditions?.logic ?? 'AND',
  );
  const [conditions, setConditions] = useState<RuleCondition[]>(
    initialConditions?.conditions ?? [{ type: 'from_contains', value: '' }],
  );
  const [isActive, setIsActive] = useState(initialActive);

  const addCondition = () => {
    setConditions([...conditions, { type: 'from_contains', value: '' }]);
  };

  const removeCondition = (index: number) => {
    setConditions(conditions.filter((_, i) => i !== index));
  };

  const updateConditionType = (index: number, type: ConditionType) => {
    const updated = [...conditions];
    updated[index] = {
      type,
      value: type === 'has_attachment' ? true : type === 'body_keywords' ? [] : '',
    };
    setConditions(updated);
  };

  const updateConditionValue = (index: number, value: string) => {
    const updated = [...conditions];
    const cond = updated[index];
    if (cond.type === 'body_keywords') {
      updated[index] = { ...cond, value: value.split(',').map((s) => s.trim()) };
    } else if (cond.type === 'has_attachment') {
      updated[index] = { ...cond, value: value === 'true' };
    } else {
      updated[index] = { ...cond, value };
    }
    setConditions(updated);
  };

  const handleSave = () => {
    if (!name.trim() || conditions.length === 0) return;
    onSave(name.trim(), { logic, conditions }, isActive);
  };

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.label}>Rule Name</Text>
      <TextInput
        style={styles.input}
        value={name}
        onChangeText={setName}
        placeholder="e.g. Urgent from boss"
      />

      <View style={styles.row}>
        <Text style={styles.label}>Active</Text>
        <Switch value={isActive} onValueChange={setIsActive} />
      </View>

      <View style={styles.logicRow}>
        <Text style={styles.label}>Match</Text>
        <TouchableOpacity
          style={[styles.logicBtn, logic === 'AND' && styles.logicActive]}
          onPress={() => setLogic('AND')}
        >
          <Text style={logic === 'AND' ? styles.logicActiveText : styles.logicText}>
            ALL
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.logicBtn, logic === 'OR' && styles.logicActive]}
          onPress={() => setLogic('OR')}
        >
          <Text style={logic === 'OR' ? styles.logicActiveText : styles.logicText}>
            ANY
          </Text>
        </TouchableOpacity>
      </View>

      {conditions.map((cond, index) => (
        <View key={index} style={styles.conditionCard}>
          <View style={styles.conditionHeader}>
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              {CONDITION_TYPES.map((ct) => (
                <TouchableOpacity
                  key={ct.type}
                  style={[
                    styles.typeChip,
                    cond.type === ct.type && styles.typeChipActive,
                  ]}
                  onPress={() => updateConditionType(index, ct.type)}
                >
                  <Text
                    style={
                      cond.type === ct.type
                        ? styles.typeChipActiveText
                        : styles.typeChipText
                    }
                  >
                    {ct.label}
                  </Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>

          {cond.type !== 'has_attachment' && (
            <TextInput
              style={styles.conditionInput}
              value={
                Array.isArray(cond.value)
                  ? (cond.value as string[]).join(', ')
                  : String(cond.value)
              }
              onChangeText={(text) => updateConditionValue(index, text)}
              placeholder={
                cond.type === 'body_keywords'
                  ? 'keyword1, keyword2, ...'
                  : 'Enter value...'
              }
            />
          )}

          {conditions.length > 1 && (
            <TouchableOpacity
              style={styles.removeBtn}
              onPress={() => removeCondition(index)}
            >
              <Text style={styles.removeBtnText}>Remove</Text>
            </TouchableOpacity>
          )}
        </View>
      ))}

      <TouchableOpacity style={styles.addBtn} onPress={addCondition}>
        <Text style={styles.addBtnText}>+ Add Condition</Text>
      </TouchableOpacity>

      <View style={styles.actions}>
        <TouchableOpacity style={styles.cancelBtn} onPress={onCancel}>
          <Text style={styles.cancelBtnText}>Cancel</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.saveBtn} onPress={handleSave}>
          <Text style={styles.saveBtnText}>Save Rule</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  label: { fontSize: 14, fontWeight: '600', color: '#333', marginBottom: 6 },
  input: {
    backgroundColor: '#f5f5f5',
    borderRadius: 8,
    padding: 12,
    fontSize: 15,
    marginBottom: 16,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  logicRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
    gap: 8,
  },
  logicBtn: {
    paddingHorizontal: 16,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#ddd',
  },
  logicActive: {
    backgroundColor: '#4A90D9',
    borderColor: '#4A90D9',
  },
  logicText: { color: '#666', fontSize: 13 },
  logicActiveText: { color: '#fff', fontSize: 13, fontWeight: '600' },
  conditionCard: {
    backgroundColor: '#f9f9f9',
    borderRadius: 8,
    padding: 12,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#eee',
  },
  conditionHeader: { marginBottom: 8 },
  typeChip: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    backgroundColor: '#eee',
    marginRight: 6,
  },
  typeChipActive: { backgroundColor: '#4A90D9' },
  typeChipText: { fontSize: 12, color: '#666' },
  typeChipActiveText: { fontSize: 12, color: '#fff', fontWeight: '500' },
  conditionInput: {
    backgroundColor: '#fff',
    borderRadius: 6,
    padding: 10,
    fontSize: 14,
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  removeBtn: { marginTop: 8, alignSelf: 'flex-end' },
  removeBtnText: { color: '#f44336', fontSize: 13 },
  addBtn: {
    padding: 12,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#4A90D9',
    borderRadius: 8,
    borderStyle: 'dashed',
    marginBottom: 20,
  },
  addBtnText: { color: '#4A90D9', fontWeight: '500' },
  actions: { flexDirection: 'row', gap: 12, marginBottom: 40 },
  cancelBtn: { flex: 1, padding: 14, borderRadius: 8, backgroundColor: '#f5f5f5', alignItems: 'center' },
  cancelBtnText: { color: '#666', fontWeight: '600' },
  saveBtn: { flex: 1, padding: 14, borderRadius: 8, backgroundColor: '#4A90D9', alignItems: 'center' },
  saveBtnText: { color: '#fff', fontWeight: '600' },
});
