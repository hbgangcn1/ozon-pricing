import React from 'react'
import { Input } from '../../components/ui/input'
import { RadioGroup } from '../../components/ui/radio-group'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select'
import { FormField, FormRow, RadioLabel, SectionTitle } from './LogisticsFormFields'

export default function LogisticsPricingSection({ form, onFormFieldChange }) {
  return (
    <div>
      <SectionTitle>计费方式</SectionTitle>
      <div className="space-y-4">
        <FormField label="计费模式">
          <RadioGroup
            value={form.fee_mode}
            onValueChange={(value) => onFormFieldChange('fee_mode', value)}
            className="flex flex-wrap gap-4"
          >
            <RadioLabel label="基础费用+续重费用" value="base_plus_continue" itemClassName="mt-0.5" />
            <RadioLabel label="首重费用+续重费用" value="first_weight" itemClassName="mt-0.5" />
          </RadioGroup>
        </FormField>

        <FormRow>
          {form.fee_mode === 'first_weight' ? (
            <FormField label="首重费用">
              <Input
                type="number"
                step="0.01"
                min="0"
                value={form.first_fee}
                onChange={(event) => onFormFieldChange('first_fee', event.target.value)}
                placeholder="0.00"
              />
            </FormField>
          ) : (
            <FormField label="基础费用">
              <Input
                type="number"
                step="0.01"
                min="0"
                value={form.base_fee}
                onChange={(event) => onFormFieldChange('base_fee', event.target.value)}
                placeholder="0.00"
              />
            </FormField>
          )}
          <FormField label="续重费用">
            <Input
              type="number"
              step="0.00001"
              min="0"
              value={form.continue_fee}
              onChange={(event) => onFormFieldChange('continue_fee', event.target.value)}
              placeholder="0.00000"
            />
          </FormField>
        </FormRow>

        {form.fee_mode === 'first_weight' && (
          <FormRow className="mt-3">
            <FormField label="首重重量(克)" tooltip="首重范围内的重量上限，单位为克">
              <Input
                type="number"
                step="1"
                min="0"
                value={form.first_weight_g}
                onChange={(event) => onFormFieldChange('first_weight_g', event.target.value)}
                placeholder="0"
              />
            </FormField>
          </FormRow>
        )}

        <FormRow className="mt-3">
          <FormField label="续重单位">
            <Select value={form.continue_unit} onValueChange={(value) => onFormFieldChange('continue_unit', value)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="g">克</SelectItem>
                <SelectItem value="1g">1克</SelectItem>
                <SelectItem value="50g">50克</SelectItem>
                <SelectItem value="100g">100克</SelectItem>
                <SelectItem value="500g">500克</SelectItem>
                <SelectItem value="1kg">1千克</SelectItem>
              </SelectContent>
            </Select>
          </FormField>
        </FormRow>
      </div>
    </div>
  )
}
