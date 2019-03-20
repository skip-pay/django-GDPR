# Generated by Django 2.1.5 on 2019-01-07 16:35

import django.db.models.deletion
from django.db import migrations, models

import gdpr.mixins


class Migration(migrations.Migration):
    initial = True

    dependencies = []  # type: ignore

    operations = [
        migrations.CreateModel(
            name='Account',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.CharField(blank=True, max_length=256, null=True)),
                ('owner', models.CharField(blank=True, max_length=256, null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(gdpr.mixins.AnonymizationModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name='Address',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('street', models.CharField(blank=True, max_length=256, null=True)),
                ('house_number', models.CharField(blank=True, max_length=20, null=True)),
                ('city', models.CharField(blank=True, max_length=256, null=True)),
                ('post_code', models.CharField(blank=True, max_length=6, null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(gdpr.mixins.AnonymizationModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name='ContactForm',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(max_length=254)),
                ('full_name', models.CharField(max_length=256)),
            ],
            options={
                'abstract': False,
            },
            bases=(gdpr.mixins.AnonymizationModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name='Customer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('first_name', models.CharField(max_length=256)),
                ('last_name', models.CharField(max_length=256)),
                ('primary_email_address', models.EmailField(blank=True, max_length=254, null=True)),
                ('full_name', models.CharField(blank=True, max_length=256, null=True)),
                ('birth_date', models.DateField(blank=True, null=True)),
                ('personal_id', models.CharField(blank=True, max_length=10, null=True)),
                ('phone_number', models.CharField(blank=True, max_length=9, null=True)),
                ('fb_id', models.CharField(blank=True, max_length=256, null=True)),
                ('last_login_ip', models.GenericIPAddressField(blank=True, null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(gdpr.mixins.AnonymizationModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name='Email',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='emails',
                                               to='tests.Customer')),
            ],
            options={
                'abstract': False,
            },
            bases=(gdpr.mixins.AnonymizationModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('date', models.DateField(auto_now_add=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments',
                                              to='tests.Account')),
            ],
            options={
                'abstract': False,
            },
            bases=(gdpr.mixins.AnonymizationModelMixin, models.Model),
        ),
        migrations.AddField(
            model_name='address',
            name='customer',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='addresses',
                                    to='tests.Customer'),
        ),
        migrations.AddField(
            model_name='account',
            name='customer',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='accounts',
                                    to='tests.Customer'),
        ),
    ]