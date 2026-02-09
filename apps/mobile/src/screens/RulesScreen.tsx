/** Rules management screen. */

import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert as RNAlert,
  FlatList,
  RefreshControl,
  StyleSheet,
  Switch,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';

import type { Rule, RuleConditions } from '../types';
import { RuleEditor } from '../components/RuleEditor';
import api from '../services/api';

export function RulesScreen() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showEditor, setShowEditor] = useState(false);
  const [editingRule, setEditingRule] = useState<Rule | null>(null);

  const fetchRules = useCallback(async () => {
    setIsLoading(true);
    try {
      const { data } = await api.get<Rule[]>('/rules');
      setRules(data);
    } catch (error) {
      console.error('Failed to fetch rules:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  const handleSave = async (
    name: string,
    conditions: RuleConditions,
    isActive: boolean,
  ) => {
    try {
      if (editingRule) {
        await api.patch(`/rules/${editingRule.id}`, { name, conditions, is_active: isActive });
      } else {
        await api.post('/rules', { name, conditions, is_active: isActive });
      }
      setShowEditor(false);
      setEditingRule(null);
      fetchRules();
    } catch (error) {
      RNAlert.alert('Error', 'Failed to save rule');
    }
  };

  const handleDelete = (rule: Rule) => {
    RNAlert.alert('Delete Rule', `Delete "${rule.name}"?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await api.delete(`/rules/${rule.id}`);
            fetchRules();
          } catch (error) {
            RNAlert.alert('Error', 'Failed to delete rule');
          }
        },
      },
    ]);
  };

  const toggleRule = async (rule: Rule) => {
    try {
      await api.patch(`/rules/${rule.id}`, { is_active: !rule.is_active });
      setRules((prev) =>
        prev.map((r) =>
          r.id === rule.id ? { ...r, is_active: !r.is_active } : r,
        ),
      );
    } catch (error) {
      console.error('Failed to toggle rule:', error);
    }
  };

  if (showEditor) {
    return (
      <RuleEditor
        initialName={editingRule?.name}
        initialConditions={editingRule?.conditions}
        initialActive={editingRule?.is_active}
        onSave={handleSave}
        onCancel={() => {
          setShowEditor(false);
          setEditingRule(null);
        }}
      />
    );
  }

  return (
    <View style={styles.container}>
      <TouchableOpacity
        style={styles.addButton}
        onPress={() => setShowEditor(true)}
      >
        <Text style={styles.addButtonText}>+ New Rule</Text>
      </TouchableOpacity>

      <FlatList
        data={rules}
        keyExtractor={(item) => item.id}
        refreshControl={
          <RefreshControl refreshing={isLoading} onRefresh={fetchRules} />
        }
        renderItem={({ item }) => (
          <View style={styles.ruleCard}>
            <View style={styles.ruleHeader}>
              <Text style={styles.ruleName}>{item.name}</Text>
              <Switch
                value={item.is_active}
                onValueChange={() => toggleRule(item)}
              />
            </View>
            <Text style={styles.ruleInfo}>
              {item.conditions.conditions?.length ?? 0} condition(s) /{' '}
              {item.conditions.logic}
            </Text>
            <View style={styles.ruleActions}>
              <TouchableOpacity
                onPress={() => {
                  setEditingRule(item);
                  setShowEditor(true);
                }}
              >
                <Text style={styles.editText}>Edit</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={() => handleDelete(item)}>
                <Text style={styles.deleteText}>Delete</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}
        ListEmptyComponent={
          !isLoading ? (
            <View style={styles.empty}>
              <Text style={styles.emptyTitle}>No rules yet</Text>
              <Text style={styles.emptyText}>
                Create a rule to get notified about important emails.
              </Text>
            </View>
          ) : null
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f5f5' },
  addButton: {
    backgroundColor: '#4A90D9',
    margin: 16,
    padding: 14,
    borderRadius: 10,
    alignItems: 'center',
  },
  addButtonText: { color: '#fff', fontSize: 15, fontWeight: '600' },
  ruleCard: {
    backgroundColor: '#fff',
    marginHorizontal: 16,
    marginBottom: 8,
    borderRadius: 10,
    padding: 14,
  },
  ruleHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  ruleName: { fontSize: 15, fontWeight: '600', color: '#333', flex: 1 },
  ruleInfo: { fontSize: 12, color: '#888', marginTop: 4 },
  ruleActions: { flexDirection: 'row', gap: 16, marginTop: 10 },
  editText: { color: '#4A90D9', fontSize: 13, fontWeight: '500' },
  deleteText: { color: '#f44336', fontSize: 13, fontWeight: '500' },
  empty: { alignItems: 'center', padding: 32 },
  emptyTitle: { fontSize: 18, fontWeight: '600', color: '#333', marginBottom: 8 },
  emptyText: { fontSize: 14, color: '#888', textAlign: 'center' },
});
